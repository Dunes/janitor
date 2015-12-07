from copy import deepcopy

__author__ = 'jack'


def make_bidirectional(edges):
    edge_ids = list(edges)
    for edge_id in edge_ids:
        rev_id = " ".join(reversed(edge_id.split(" ")))
        if rev_id in edges:
            continue

        edge = deepcopy(edges[edge_id])
        edges[rev_id] = edge

    return edges
