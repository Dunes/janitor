import sys
sys.path.append("./src")

from problem_parser import decode, encode

def reverse_edge_id(edge_id):
	return " ".join(reversed(edge_id.split(" ")))

def validate_edges(edges):
	for edge_id, value in edges.items():
		reversed_id = reverse_edge_id(edge_id)
		if edges[edge_id] != edges[reversed_id]:
			raise ValueError(edge_id)


if __name__ == "__main__":
	filename = "temp_problems/final_model.json" if len(sys.argv) == 1 else sys.argv[1]
	model = decode(filename)
	validate_edges(model["graph"]["edges"])
	print("success")
	

