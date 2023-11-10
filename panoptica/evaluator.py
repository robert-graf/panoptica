from abc import ABC, abstractmethod

import numpy as np

from result import PanopticaResult
from utils.datatypes import SemanticPair, UnmatchedInstancePair, MatchedInstancePair, _ProcessingPair, _ProcessingPairInstanced
from instance_approximator import InstanceApproximator
from instance_matcher import InstanceMatchingAlgorithm
from instance_evaluator import evaluate_matched_instance
from timing import measure_time


class Panoptic_Evaluator:
    def __init__(
        self,
        expected_input: type(SemanticPair) | type(UnmatchedInstancePair) | type(MatchedInstancePair),
        instance_approximator: InstanceApproximator | None,
        instance_matcher: InstanceMatchingAlgorithm | None,
        iou_threshold: float = 0.5,
    ) -> None:
        self.__expected_input = expected_input
        self.__instance_approximator = instance_approximator
        self.__instance_matcher = instance_matcher
        self.__iou_threshold = iou_threshold

    @measure_time
    def evaluate(self, processing_pair: _ProcessingPair) -> tuple[PanopticaResult, dict[str, _ProcessingPair]]:
        assert type(processing_pair) == self.__expected_input, f"input not of expected type {self.__expected_input}"
        return panoptic_evaluate(
            processing_pair=processing_pair,
            instance_approximator=self.__instance_approximator,
            instance_matcher=self.__instance_matcher,
            iou_threshold=self.__iou_threshold,
        )


def panoptic_evaluate(
    processing_pair: SemanticPair | UnmatchedInstancePair | MatchedInstancePair | PanopticaResult,
    instance_approximator: InstanceApproximator | None,
    instance_matcher: InstanceMatchingAlgorithm | None,
    iou_threshold: float,
    verbose: bool = False,
    **kwargs,
) -> tuple[PanopticaResult, dict[str, _ProcessingPair]]:
    debug_data: dict[str, _ProcessingPair] = {}
    # First Phase: Instance Approximation
    if isinstance(processing_pair, PanopticaResult):
        return processing_pair, debug_data

    if isinstance(processing_pair, SemanticPair):
        assert instance_approximator is not None, "Got SemanticPair but not InstanceApproximator"
        processing_pair = instance_approximator.approximate_instances(processing_pair)
        debug_data["UnmatchedInstanceMap"] = processing_pair.copy()

    # Second Phase: Instance Matching
    if isinstance(processing_pair, UnmatchedInstancePair):
        processing_pair = _handle_zero_instances_cases(processing_pair)

    if isinstance(processing_pair, UnmatchedInstancePair):
        assert instance_matcher is not None, "Got UnmatchedInstancePair but not InstanceMatchingAlgorithm"
        processing_pair = instance_matcher.match_instances(processing_pair)
        debug_data["MatchedInstanceMap"] = processing_pair.copy()

    # Third Phase: Instance Evaluation
    if isinstance(processing_pair, MatchedInstancePair):
        processing_pair = _handle_zero_instances_cases(processing_pair)

    if isinstance(processing_pair, MatchedInstancePair):
        processing_pair = evaluate_matched_instance(processing_pair, iou_threshold=iou_threshold)

    if isinstance(processing_pair, PanopticaResult):
        return processing_pair, debug_data

    raise RuntimeError("End of panoptic pipeline reached without results")


def _handle_zero_instances_cases(
    processing_pair: UnmatchedInstancePair | MatchedInstancePair,
) -> UnmatchedInstancePair | MatchedInstancePair | PanopticaResult:
    """
    Handle edge cases when comparing reference and prediction masks.

    Args:
        num_ref_instances (int): Number of instances in the reference mask.
        num_pred_instances (int): Number of instances in the prediction mask.

    Returns:
        PanopticaResult: Result object with evaluation metrics.
    """
    n_reference_instance = processing_pair.n_reference_instance
    n_prediction_instance = processing_pair.n_prediction_instance
    # Handle cases where either the reference or the prediction is empty
    if n_prediction_instance == 0 or n_reference_instance == 0:
        # Both references and predictions are empty, perfect match
        return PanopticaResult(
            num_ref_instances=0,
            num_pred_instances=0,
            tp=0,
            dice_list=[],
            iou_list=[],
        )
    if n_reference_instance == 0:
        # All references are missing, only false positives
        return PanopticaResult(
            num_ref_instances=0,
            num_pred_instances=n_prediction_instance,
            tp=0,
            dice_list=[],
            iou_list=[],
        )
    if n_prediction_instance == 0:
        # All predictions are missing, only false negatives
        return PanopticaResult(
            num_ref_instances=n_reference_instance,
            num_pred_instances=0,
            tp=0,
            dice_list=[],
            iou_list=[],
        )
    return processing_pair


if __name__ == "__main__":
    from instance_approximator import ConnectedComponentsInstanceApproximator, CCABackend
    from instance_matcher import NaiveOneToOneMatching
    from instance_evaluator import evaluate_matched_instance

    a = np.zeros([50, 50], dtype=int)
    b = a.copy()
    a[20:40, 10:20] = 1
    b[20:35, 10:20] = 2

    sample = SemanticPair(b, a)

    evaluator = Panoptic_Evaluator(
        expected_input=SemanticPair,
        instance_approximator=ConnectedComponentsInstanceApproximator(cca_backend=CCABackend.cc3d),
        instance_matcher=NaiveOneToOneMatching(),
    )

    result, debug_data = evaluator.evaluate(sample)
    print(result)
