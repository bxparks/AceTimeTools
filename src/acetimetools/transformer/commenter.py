# Copyright 2022 Brian T. Park
#
# MIT License.

import logging
from typing import List
from typing import Optional
from typing import Set
from typing import Union
from typing import cast

from acetimetools.data_types.at_types import CommentsMap
from acetimetools.data_types.at_types import MergedCommentsMap
from acetimetools.data_types.at_types import PoliciesMap
from acetimetools.data_types.at_types import TransformerResult
from acetimetools.data_types.at_types import ZonesMap
from acetimetools.data_types.at_types import ZonesToPolicies
from acetimetools.data_types.at_types import add_comment
from acetimetools.data_types.at_types import merge_comments


class Commenter:
    """Update notable zone and policy comments.
    """

    def __init__(
        self,
        tresult: TransformerResult,
    ):
        self.tresult = tresult

    def transform(self) -> None:
        _note_zones_with_odd_utc_offset(
            self.tresult.zones_map,
            self.tresult.policies_map,
            self.tresult.notable_zones,
        )

        self.zones_to_policies = _gather_zones_to_policies(
            self.tresult.zones_map,
            self.tresult.policies_map,
        )

        self.merged_notable_zones = _create_merged_comments_map(
            self.tresult.notable_zones,
            self.tresult.notable_policies,
            self.zones_to_policies,
        )

    def print_summary(self) -> None:
        zone_count = len(self.merged_notable_zones)
        comment_count = _count_merged_counts_map(self.merged_notable_zones)
        logging.info(f"Zones: {zone_count}; Comments: {comment_count}")

    def get_data(self) -> TransformerResult:
        return TransformerResult(
            zones_map=self.tresult.zones_map,
            policies_map=self.tresult.policies_map,
            links_map=self.tresult.links_map,
            removed_zones=self.tresult.removed_zones,
            removed_policies=self.tresult.removed_policies,
            removed_links=self.tresult.removed_links,
            notable_zones=self.tresult.notable_zones,
            zones_to_policies=self.zones_to_policies,
            merged_notable_zones=self.merged_notable_zones,
            notable_policies=self.tresult.notable_policies,
            notable_links=self.tresult.notable_links,
            zone_ids=self.tresult.zone_ids,
            link_ids=self.tresult.link_ids,
            letters_per_policy=self.tresult.letters_per_policy,
            letters_map=self.tresult.letters_map,
            formats_map=self.tresult.formats_map,
            fragments_map=self.tresult.fragments_map,
            compressed_names=self.tresult.compressed_names,
        )


def _gather_zones_to_policies(
    zones_map: ZonesMap,
    policies_map: PoliciesMap,
) -> ZonesToPolicies:
    """
    Create a map of zone names to its list of policy names which are used
    by that zone.
    """
    zones_to_policies: ZonesToPolicies = {}
    for zone_name, eras in zones_map.items():
        for era in eras:
            rule_name = era['rules']
            if rule_name not in [':', '-']:
                policies = cast(
                    Optional[Set[str]],
                    zones_to_policies.get(zone_name)
                )
                if policies is None:
                    policies = set()
                    zones_to_policies[zone_name] = policies
                policies.add(rule_name)
    return zones_to_policies


def _create_merged_comments_map(
    zone_comments: CommentsMap,
    policy_comments: CommentsMap,
    zones_to_policies: ZonesToPolicies,
) -> MergedCommentsMap:
    """Merge the zone policy comments into the zone info comments.
    """

    merged_comments: MergedCommentsMap = {}

    # Pass 1: Copy the zone comments.
    for name, reasons in sorted(zone_comments.items()):
        # Copy the zone comments.
        merged_reasons: List[Union[str, CommentsMap]] = list(reasons)
        merged_reasons.sort()
        merged_comments[name] = merged_reasons

    # Pass 2: Add the policy notes.
    for zone_name, policies in zones_to_policies.items():

        # Extract the policy comments for the given zone.
        sub_policies_map: CommentsMap = {}
        for policy in policies:
            entry = policy_comments.get(policy)
            if entry is not None:
                comments = list(entry)
                comments.sort()
                sub_policies_map[policy] = comments

        # Add to the merged_reasons.
        if sub_policies_map:
            policy_reasons = merged_comments.get(zone_name)
            if policy_reasons is None:
                policy_reasons = list()
                merged_comments[zone_name] = policy_reasons
            policy_reasons.append(sub_policies_map)

    return merged_comments


def _count_merged_counts_map(comments: MergedCommentsMap) -> int:
    count = 0
    for zone_name, reasons in comments.items():
        for reason in reasons:
            if isinstance(reason, str):
                count += 1
            else:
                for policy_name, policy_reasons in reason.items():
                    for policy_reason in policy_reasons:
                        count += 1
    return count


def _note_zones_with_odd_utc_offset(
    zones_map: ZonesMap,
    policies_map: PoliciesMap,
    all_notable_zones: CommentsMap,
) -> None:
    """Note zones whose UTC offset is not at :00 or :30 mark into the
    'all_notable_zones' map.
    """
    notable_zones: CommentsMap = {}
    for zone_name, eras in zones_map.items():
        for era in eras:
            # Check the STDOFF column for non :00 or :30
            if era['offset_seconds'] % 1800 != 0:
                offset_string = era['offset_string']
                add_comment(
                    notable_zones, zone_name,
                    f'STDOFF ({offset_string}) not at :00 or :30 mark')
                break

            # Check the RULES column, which has 3 options: a policy name,
            # '-', or ':'.
            rule_name = era['rules']
            found_odd_offset = False
            if rule_name == ':':
                if era['rules_delta_seconds'] % 1800 != 0:
                    add_comment(
                        notable_zones, zone_name,
                        f'RULES ({rule_name}) not at :00 or :30 mark')
            elif rule_name != '-':
                # RULES contains a reference to a policy
                rules = policies_map.get(rule_name)
                assert rules is not None
                for rule in rules:
                    # Check SAVE column for non :00 or :30
                    save_string = rule['delta_offset']
                    if rule['delta_seconds'] % 1800 != 0:
                        add_comment(
                            notable_zones, zone_name,
                            f'SAVE ({save_string}) in Rule {rule_name}'
                            f' not at :00 or :30 mark')
                        found_odd_offset = True
                        break
            if found_odd_offset:
                break

    merge_comments(all_notable_zones, notable_zones)
