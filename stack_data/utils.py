from collections import OrderedDict


def truncate(seq, max_length, middle):
    if len(seq) > max_length:
        left = (max_length - len(middle)) // 2
        right = max_length - len(middle) - left
        seq = seq[:left] + middle + seq[-right:]
    return seq


def unique_in_order(it):
    return list(OrderedDict.fromkeys(it))


def line_range(node):
    return (
        node.first_token.start[0],
        node.last_token.end[0] + 1,
    )
