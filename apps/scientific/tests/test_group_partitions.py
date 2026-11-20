import pytest

from apps.scientific.app.domains.execution.domain_execution import (
    validate_group_partition_disjointness,
)


def test_group_partitions_accept_disjoint_groups():
    validate_group_partition_disjointness(
        training_groups=["lake-1", "lake-2"],
        evaluation_groups=["lake-3"],
    )


def test_group_partitions_reject_shared_groups():
    with pytest.raises(ValueError, match="lake-2"):
        validate_group_partition_disjointness(
            training_groups=["lake-1", "lake-2"],
            evaluation_groups=["lake-2", "lake-3"],
        )
