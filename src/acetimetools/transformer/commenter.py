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


class Commenter:
    """Merge the comments for each ZonePolicy into the ZoneInfo records which
    use those ZonePolicies.
    """

    def __init__(self) -> None:
        pass

    def transform(self, tresult: TransformerResult) -> None:
        tresult.zones_to_policies = _gather_zones_to_policies(
            tresult.zones_map,
            tresult.policies_map,
        )

        tresult.merged_notable_zones = _create_merged_comments_map(
            tresult.notable_zones,
            tresult.notable_policies,
            tresult.zones_to_policies,
        )

    def print_summary(self, tresult: TransformerResult) -> None:
        zone_count = len(tresult.merged_notable_zones)
        comment_count = _count_merged_counts_map(tresult.merged_notable_zones)
        logging.info(f"Zones: {zone_count}; Comments: {comment_count}")


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
            policy_name = era['policy_name']
            if policy_name:
                policies = cast(
                    Optional[Set[str]],
                    zones_to_policies.get(zone_name)
                )
                if policies is None:
                    policies = set()
                    zones_to_policies[zone_name] = policies
                policies.add(policy_name)
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
