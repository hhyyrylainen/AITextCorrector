from typing import List
from Levenshtein import distance as levenshtein_distance

DEFAULT_THRESHOLD = 0.5


def validate_corrections(original: List[str], corrections: List[str], threshold: float = DEFAULT_THRESHOLD,
                         all_must_pass: bool = False) -> bool:
    """
    Validate that the second list of paragraphs contains corrected versions of the first list.

    Args:
        original (List[str]): The original list of paragraphs.
        corrections (List[str]): The corrected list of paragraphs.
        threshold (float): Maximum relative Levenshtein distance allowed for a correction
                           (for example 0.2 means 20% of the original paragraph length).
        all_must_pass (bool): If True, all corrections must pass the validation check (instead of just the average).
    Returns:
        bool: True if all corrections are valid; False otherwise.
    """
    # Ensure both lists are the same length
    if len(original) != len(corrections):
        raise ValueError("Original and corrected lists must have the same length.")

    # Assume empty is fine
    if len(original) == 0:
        return True

    distance_values = []

    for i, (orig, corr) in enumerate(zip(original, corrections)):
        # Compute the Levenshtein distance between the original and the corrected paragraph
        dist = levenshtein_distance(orig, corr)

        # Calculate relative distance (distance as a proportion of the original paragraph's length)
        if len(orig) > 0:
            relative_dist = dist / len(orig)
        else:
            # TODO: maybe allow empty correction?
            return False  # If original paragraph is empty, reject any correction

        distance_values.append(relative_dist)

        # Check if the relative distance exceeds the allowed threshold
        if all_must_pass and relative_dist > threshold:
            print(
                f"Correction at index {i} is invalid: {relative_dist * 100:.2f}% change (allowed: {threshold * 100:.2f}%)")
            return False  # Reject if the correction deviates too much from the original

    average = sum(distance_values) / len(original)
    if average > threshold:
        print(f"Average correction distance exceeds threshold ({average * 100:.2f}% > {threshold * 100:.2f}%).")
        return False

    # If all corrections pass the check, return True
    return True
