# Copyright 2022 Brian T. Park
#
# MIT License.

import logging
from typing import List
from typing import Union

from acetimetools.data_types.at_types import CommentsMap
from acetimetools.data_types.at_types import MergedCommentsMap
from acetimetools.data_types.at_types import ZonesToPolicies
from acetimetools.data_types.at_types import TransformerResult


class Commenter:
    """
    Merge zone policy comments into the zone info comments after all
    transformations.
    """
    def __init__(
        self,
        tresult: TransformerResult,
    ):
        self.tresult = tresult

    def transform(self) -> None:
        """Merge zone policy comments into zone info comments.
        """
        self.merged_notable_zones = _create_merged_comments_map(
            self.tresult.notable_zones,
            self.tresult.notable_policies,
            self.tresult.zones_to_policies,
        )

    def print_summary(self) -> None:
        zone_count = len(self.merged_notable_zones)
        comment_count = _count_merged_counts_map(self.merged_notable_zones)
        logging.info(f"Zones: {zone_count}; Comments: {comment_count}")

    def get_data(self) -> TransformerResult:
        """Merge the result of transform() into the original tresult."""

        return TransformerResult(
            zones_map=self.tresult.zones_map,
            policies_map=self.tresult.policies_map,
            links_map=self.tresult.links_map,
            zones_to_policies=self.tresult.zones_to_policies,
            removed_zones=self.tresult.removed_zones,
            removed_policies=self.tresult.removed_policies,
            removed_links=self.tresult.removed_links,
            notable_zones=self.tresult.notable_zones,
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
        merged_comments[name] = merged_reasons

    # Pass 2: Add the policy notes.
    for zone_name, policies in sorted(zones_to_policies.items()):

        # Extract the policy comments for the given zone.
        sub_policies_map: CommentsMap = {}
        for policy in policies:
            entry = policy_comments.get(policy)
            if entry is not None:
                sub_policies_map[policy] = entry

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
