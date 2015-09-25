ELEMENT_CONSTS = {
	node: {
		width: 30,
		height: 30,
		colour: {
			hospital: "green", 
			building: "grey"
		}
	},
	edge: {
		width: 5,
		colour: {
			blocked: "red",
			unblocked: "aqua",
		}
	},
	agent: {
		radius: 15,
		gap: 5,
		colour: {
			medic: "lime",
			police: "blue",
			civilian: "olive"
		}
	},
	text: {
		offset: {
			first_x: 10,
			first_y: 40,
			x: 0,
			y: 30
		},
		font: {
			size: "24pt",
			family: "arial"
		}
	}
}


function drawLayout($) {
    try {
        var data = parseData($, $("#input-data").val().trim());
        var elements = createElements(data);
        $("#canvas").html(elements);
        // hack to force refresh of svg canvas
        $("#canvas-container").html($("#canvas-container").html());
    } catch (err) {
        $("#error-log").html(err);
    }
}

function parseData($, data_string) {;
	var data = $.parseJSON(data_string);
	return {	
		nodes: parseNodes(data.objects.building, data.objects.hospital),
		agents: parseAgents(data.objects.medic, data.objects.police, data.objects.civilian),
		edges: parseEdges(data.graph.edges)
	}
}


function parseNodes(buildings, hospitals) {
	var nodes = {};
	for (var key in buildings) {
		nodes[key] = parseNode(key, buildings[key]);
	}
	for (var key in hospitals) {
		nodes[key] = parseNode(key, hospitals[key]);
	}
	return nodes;
}

function parseNode(id, data) {
	var [type, x, y] = parseNodeId(id);
	var type = /[^0-9]+/.exec(id);
	var coord = /[0-9]+-[0-9]+/.exec(id);
	if (type == null || coord == null) {
		throw "malformed node id: " + id;
	}
	var [x, y] = coord[0].split("-").map(Number);
	return new Node(type[0], new Point(x, y), data);
}

function parseNodeId(id) {
	var type = /[^0-9]+/.exec(id);
	var coord = /[0-9]+-[0-9]+/.exec(id);
	if (type == null || coord == null) {
		throw "malformed node id: " + id;
	}
	var [x, y] = coord[0].split("-").map(Number);
	return [type, x, y];
}

function parseAgents(medics, police, civilians) {
	var agents = {};
	$.each(medics, function (key, value) {
		agents[key] = new Agent("medic", value.at[1]);
	});
	$.each(police, function (key, value) {
		agents[key] = new Agent("police", value.at[1]);
	});
	$.each(civilians, function (key, value) {
		var value = $.extend({}, value.known, value.unknown);
		agents[key] = new Agent("civilian", value.at[1]);
	});
	return agents;
}


function parseEdges(edges) {
	var edge_objects = {};
	for (var key in edges) {
		var id = key.split(" ");
		id.sort();
		var key = id[0] + " " + id[1];
		if (edge_objects[key] !== undefined) {
			continue;
		}
		edge_objects[key] = parseEdge(id[0], id[1], edges[key]);
	}
	return edge_objects;
}

function parseEdge(from, to, edge) {
	var combined = $.extend({}, edge.known, edge.unknown);
	return new Edge(from, to, combined.distance, combined["blocked-edge"] === true, combined.blockedness);
}



function createElements(data) {
	var map = new Map(data);
	
	var nodes = createNodeElements(data.nodes, map);
	var edges = createEdgeElements(data.edges, data.nodes, map);
	var agents = createAgentElements(data.agents, data.nodes, map);
	
	var elements = [];
	$.merge(elements, $.map(edges, function(item) {return item;}));
	$.merge(elements, $.map(nodes, function(item) {return item;}));
	$.merge(elements, $.map(agents, function(item) {return item;}));
	
	return elements;
}

function Map(data) {
	$.extend(this, ELEMENT_CONSTS);
	var canvas = $("#canvas");
	this.dimensions = $.extend({}, document.getElementById("canvas").viewBox.baseVal);
	var width = 0, height = 0;
	for (var id in data.nodes) {
		var pos = data.nodes[id].position;
		width = Math.max(width, pos.x);
		height = Math.max(height, pos.y);
	}
	this.width = width + 1;
	this.height = height + 1;
	this.border = {
		width: this.dimensions.width / (2 * this.width),
		height: this.dimensions.height / (2 * this.height)
	};
}

Map.prototype.getNodeX = function (x) {
	return this.dimensions.width * (x / this.width) + this.border.width;
}

Map.prototype.getNodeY = function (y) {
	return this.dimensions.height * (y / this.height) + this.border.height;
}

function createNodeElements(nodes, map) {
	var elements = {};
	$.each(nodes, function (key, value) {
		var e = $("<rect>");
		e.attr("x", map.getNodeX(value.position.x));
		e.attr("y", map.getNodeY(value.position.y));
		e.attr("width", map.node.width);
		e.attr("height", map.node.height);
		e.attr("fill", map.node.colour[value.type]);
		elements[key] = e;	
	});
	return elements;
}

function createEdgeElements(edges, nodes, map) {
	var edge_elements = {};
	$.each(edges, function (key, value) {
		var node_pos = nodes[value.from].position;
		var x1 = map.getNodeX(node_pos.x) + map.node.width / 2;
		var y1 = map.getNodeY(node_pos.y) + map.node.height / 2;
		node_pos = nodes[value.to].position;
		var x2 = map.getNodeX(node_pos.x) + map.node.width / 2;
		var y2 = map.getNodeY(node_pos.y) + map.node.height / 2;
		
		var e = $("<line>");
		e.attr("x1", x1);
		e.attr("y1", y1);
		e.attr("x2", x2);
		e.attr("y2", y2);
		e.attr("stroke-width", map.edge.width);
		e.attr("stroke", value.blocked ? map.edge.colour.blocked : map.edge.colour.unblocked);
		edge_elements[key] = e;
		
		var distance = createTextElement("distance: " + value.distance, 
			(x1 + x2) / 2, 
			(y1 + y2) / 2, 
			map); 
		edge_elements[key+"-distance"] = distance;
		
		if (value.blockedness) {
			var blockedness = createTextElement("blockedness: " + value.blockedness, 
				((x1 + x2) / 2) + map.text.offset.x, 
				((y1 + y2) / 2) + map.text.offset.y, 
				map); 
			edge_elements[key+"-blockedness"] = blockedness;
		}
	});
	return edge_elements;
}

function createTextElement(text, x, y, map) {
	var e = $("<text>");
	e.text(text);
	e.attr("x", x + map.text.offset.first_x);
	e.attr("y", y + map.text.offset.first_y);
	e.attr("font-family", map.text.font.family);
	e.attr("font-size", map.text.font.size);
	return e;
}

function createAgentElements(agents, nodes, map) {
	var agent_elements = {};
	var node_population = {};
	$.each(nodes, function(key, value) {
		node_population[key] = 0;
	});
	
	$.each(agents, function (key, value) {
		
		var node_pos = nodes[value.node].position;
		var x = map.getNodeX(node_pos.x) + map.node.width + map.agent.radius + node_population[value.node] * (map.agent.radius * 2 + map.agent.gap);
		var y = map.getNodeY(node_pos.y) + map.node.height + map.agent.radius;
		
		var e = $("<circle>");
		e.attr("cx", x);
		e.attr("cy", y);
		e.attr("r", map.agent.radius);
		e.attr("fill", map.agent.colour[value.type]);
		
		agent_elements[key] = e;
		
		node_population[value.node] += 1;
	});
	return agent_elements;
}

// classes

function Point(x, y) {
	this.x = x;
	this.y = y;
}

Point.prototype.toString = function() {
	return "Point("+this.x+", "+this.y+")";
}

function Node(type, position, data) {
	this.type = type;
	this.position = position;
	$.extend(this, data);
}

Node.prototype.toString = function() {
	return "Node(\""+this.type+"\", "+this.position+")";
}

function Edge(from, to, distance, blocked, blockedness) {
	this.from = from;
	this.to = to;
	this.distance = distance;
	this.blocked = blocked;
	this.blockedness = blockedness;
}

Edge.prototype.toString = function() {
	return "Edge(\""+this.from+" "+this.to+"\")";
}

function Agent(type, node) {
	this.type = type;
	this.node = node;
}
