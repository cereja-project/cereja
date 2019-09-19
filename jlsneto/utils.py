from typing import Any, List


def group_items_in_batches(items: List[Any], items_per_batch: int = 0) -> List[List[Any]]:
    """
    Responsible for grouping items in batch taking into account the quantity of items per batch

    :param items: list of any values
    :param items_per_batch: number of items per batch
    :return:
    """
    items_length = len(items)
    if not isinstance(items_per_batch, int):
        raise TypeError(f"Value for items_per_batch is not valid. Please send integer.")
    if items_per_batch < 0 or items_per_batch > len(items):
        raise ValueError(f"Value for items_per_batch is not valid. I need a number integer between 0 and {len(items)}")
    if items_per_batch == 0:
        return items

    batches = []

    for i in range(0, items_length, items_per_batch):
        batch = [group for group in items[i:i + items_per_batch]]
        batches.append(batch)
    return batches
