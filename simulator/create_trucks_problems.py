import json
from random import choice

root = "problems/trucks/split"

PACKAGE_RATIO = 0.5 # round up to div by 2?
PACKAGE_RATIO_INTER_NETWORK = 2
EDGE_COST = {
    "land": 60,
    "sea": 30,
}
DOMAIN_NAME = "trucks-modified"
VEHICLE_AREAS = 2


class Graph:
    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges


def create_model(width, height, packages, trucks, boats, problem_name):
    graph = create_graph(width, height)
    objects = create_object(packages, trucks, boats, graph)
    goals = create_goals(objects)
    metric = create_metric()

    model = {
        "domain": DOMAIN_NAME,
        "problem": problem_name,
        "goal": goals,
        "metric": metric,
        "assumed-values": {
        },
        "objects": objects,
        "graph": {
            "bidirectional": False,
            "edges": graph.edges
        },
    }

    return model


def create_graph(width, height):
    assert width == height
    n = width * height
    n_top = n // 2
    n_bot = n - n_top

    n_ports = max(1, width // 4) * 2
    half_n_ports = n_ports // 2

    linear_nodes = ['land'] * n_top + ['sea'] * n_bot
    node_list = [linear_nodes[i:i+width] for i in range(0, n, width)]

    bot_row_i, remainder = divmod(height, 2)
    top_row_i = bot_row_i - (1 - remainder)
    node_list[bot_row_i][:half_n_ports] = ['port'] * half_n_ports
    node_list[top_row_i][-half_n_ports:] = ['port'] * half_n_ports

    def neighbours(x, y):
        if x > 0:
            yield x - 1, y
        if x < width - 1:
            yield x + 1, y
        if y > 0:
            yield x, y - 1
        if y < width - 1:
            yield x, y + 1

    def node_name(type_, w, h):
        return "{}-{}-{}".format(type_, w, h)

    nodes = {}
    edges = {}

    for h, row in enumerate(node_list):
        for w, node_type in enumerate(row):
            nodes[node_name(node_type, w, h)] = {}
            for neigh_w, neigh_h, in neighbours(w, h):
                neigh_type = node_list[neigh_h][neigh_w]
                types = {node_type, neigh_type}
                types.discard("port")
                if len(types) != 1:
                    continue  # sea and land -- no connection (or port to port)

                [conn_type] = types
                edges["{} {}".format(node_name(node_type, w, h), node_name(neigh_type, neigh_w, neigh_h))] = {
                    "connected-by-{}".format(conn_type): True,
                    "travel-time": EDGE_COST[conn_type]
                }

    return Graph(nodes, edges)


def create_object(n_packages, n_trucks, n_boats, graph):
    locations = graph.nodes

    truck_locations = [node_id for node_id in locations if not node_id.startswith("sea")]
    boat_locations = [node_id for node_id in locations if not node_id.startswith("land")]

    all_locations = list(locations)
    land_locations = [node_id for node_id in locations if node_id.startswith("land")]
    sea_locations = [node_id for node_id in locations if node_id.startswith("sea")]
    not_port_locations = [node_id for node_id in locations if not node_id.startswith("port")]

    trucks = {
        "truck{}".format(i): {
            "at": [True, choice(truck_locations)]
        }
        for i in range(n_trucks)
    }

    boats = {
        "boat{}".format(i): {
            "at": [True, choice(boat_locations)]
        }
        for i in range(n_boats)
    }

    vehicleareas = {}
    for agent_id in list(trucks) + list(boats):
        va_c = "vehiclearea-nearest-{}".format(agent_id)
        va_f = "vehiclearea-furthest-{}".format(agent_id)
        vehicleareas[va_c] = {
            "free": [True, agent_id],
        }
        vehicleareas[va_f] = {
            "free": [True, agent_id],
            "closer": [va_c, True]
        }

    packages = {}
    for i in range(n_packages // 2):
        # same network
        start = choice(all_locations)
        if start.startswith("land"):
            end_choices = land_locations
        elif start.startswith("sea"):
            end_choices = sea_locations
        elif start.startswith("port"):
            end_choices = all_locations
        else:
            assert False

        packages["package{}".format(i)] = {
            "at": [True, start],
            "deliverable": [True, choice(end_choices)],
        }

    for i in range(n_packages // 2, n_packages):
        # same network
        start = choice(not_port_locations)
        if start.startswith("land"):
            end_choices = sea_locations
        elif start.startswith("sea"):
            end_choices = land_locations
        else:
            assert False

        packages["package{}".format(i)] = {
            "at": [True, start],
            "deliverable": [True, choice(end_choices)],
        }

    return {
        "location": locations,
        "truck": trucks,
        "boat": boats,
        "package": packages,
        "vehiclearea": vehicleareas,
    }


def create_goals(objects):
    return {
        "hard-goals": [
            ["delivered", p_id, package["deliverable"][1]]
            for p_id, package in objects["package"].items()
        ]
    }


def create_metric():
    return {
        "type": "minimize",
        "predicate": [
            "total-time"
        ]
    }


def single(width, height, packages, trucks, boats, id_):
    model_name = "trucks-split-width({})-height({})-trucks({})-boats({})-id({})".format(
        width, height, trucks, boats, id_
    )

    model = create_model(width, height, packages, trucks, boats, model_name)

    json_str = json.dumps(model, indent="    ", sort_keys=True)

    out_file = "{}/{}.json".format(root, model_name)
    with open(out_file, "w") as f:
        f.write(json_str)


def main():
    for n_nodes in range(3, 11):
        for n_agents in range(3, 6):
            for id_ in range(10):
                width = n_nodes
                height = n_nodes
                packages = int(width * height * PACKAGE_RATIO)
                trucks = n_agents
                boats = n_agents
                single(
                    width=width, height=height, packages=packages, trucks=trucks, boats=boats, id_=id_
                )


if __name__ == "__main__":
    main()
