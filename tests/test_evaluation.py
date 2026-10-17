import pytest
from youseela.evaluation import evaluate_labels


def test_pilot_evaluation_counts_abstention_and_undefined_precision() -> None:
    truth = {'a':'present', 'b':'absent', 'c':'absent', 'd':'unusable'}
    predicted = {'a':'unclear', 'b':'absent', 'c':'present', 'd':'unusable'}
    report = evaluate_labels(truth, predicted)
    assert report['sample_size'] == 4
    assert report['human_label_agreement'] == .5
    assert report['per_class']['present']['precision'] == 0
    assert report['per_class']['present']['recall'] == 0
    assert report['decisive_coverage_on_clear_references'] == pytest.approx(2/3)
    assert report['selective_accuracy_on_clear_references'] == .5
    empty_positive = evaluate_labels({'a':'absent'}, {'a':'absent'})
    assert empty_positive['per_class']['present']['precision'] is None
    assert empty_positive['per_class']['present']['recall'] is None


def test_evaluation_rejects_missing_predictions_instead_of_dropping_cases() -> None:
    with pytest.raises(ValueError, match='same image IDs'):
        evaluate_labels({'a':'present', 'b':'absent'}, {'a':'present'})
