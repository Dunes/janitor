
true = True
false = False
d = {
    "agents": {
        "agent1": {
            "agent": true,
            "at": [
                true,
                "empty-rm1"
            ],
            "available": true
        },
        "agent2": {
            "agent": true,
            "at": [
                true,
                "empty-rm1"
            ],
            "available": true
        },
        "agent3": {
            "agent": true,
            "at": [
                true,
                "empty-rm1"
            ],
            "available": true
        }
    },
    "assumed-values": {
        "cleaned": false,
        "dirtiness": "max",
        "dirty": true,
        "extra-dirty": false
    },
    "domain": "janitor",
    "goal": {
        "hard-goals": [
            [
                "cleaned",
                "rm1"
            ],
        ]
    },
    "graph": {
        "bidirectional": false,
        "edges": [
            [
                "rm1",
                "rm4",
                20
            ],
        ]
    },
    "metric": {
        "predicate": [
            "total-time"
        ],
        "type": "minimize"
    },
    "nodes": {
        "empty-rm1": {
            "node": true
        },
        "rm-ed1": {
            "known": {
                "is-room": true,
                "node": true
            },
            "unknown": {
                "cleaned": {
                    "actual": false
                },
                "dirtiness": {
                    "actual": 32,
                    "max": 40,
                    "min": 20
                },
                "dirty": {
                    "actual": false
                },
                "extra-dirty": {
                    "actual": true
                }
            }
        },
    },
    "problem": ...
}



import argparse
import json
from pathlib import Path


def get_parser():
    parser_ = argparse.ArgumentParser()
    parser_.add_argument("--src", "-s", type=Path, required=True)
    return parser_


def main(src: Path):
    for filename in src.iterdir():
        assert filename.exists()
        if not filename.suffix == '.json':
            continue

        with filename.open() as f:
            model = json.load(f)

        if "objects" not in model:
            continue

        convert_objects(model)
        convert_graph(model)

        with filename.open("w") as f:
            json.dump(model, f, indent='    ', sort_keys=True)


def convert_objects(model):
    agents = model['agents'] = {}

    for agent_name, agent_value in model['objects']['agent'].items():
        agent_value = dict(agent_value)
        agent_value['agent'] = True
        agents[agent_name] = agent_value

    nodes = model['nodes'] = {}

    for room_name, room_value in model['objects']['room'].items():
        room_value = dict(room_value)
        room_value['known']['node'] = True
        room_value['known']['is-room'] = True
        nodes[room_name] = room_value

    for node_name, node_value in model['objects']['node'].items():
        nodes[node_name] = {"node": True}

    del model['objects']


def convert_graph(model):
    new_edges = []
    for name, value in model['graph']['edges'].items():
        edge = name.split()
        edge.append(value['known']['distance'])
        new_edges.append(edge)

    model['graph']['edges'] = new_edges


if __name__ == "__main__":
    main(**vars(get_parser().parse_args()))
