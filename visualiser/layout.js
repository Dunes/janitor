"use strict";

var ELEMENT_CONSTS = {
	node: {
		width: 30,
		height: 30,
		colour: {
			hospital: "green", 
			building: "grey"
		}
	},
	edge: {
		width: 10,
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


var OBJECT_TYPES = ["medic", "police", "civilian", "building", "hospital"];


var OBJECT_FIELD_CREATOR = {
	default_: function (key, value) {
		if (value === true || value === false) {
			return $("<input>", {type: "checkbox", name: key, checked: value})
		} 
		return $("<input>", {name: key, value: value});
	},
	id: function () {
		return null;
	},
	type: function () {
		return null;
	},
	at: function (key, value) {
		var current_node = value[1];
		var locations = $.extend({}, model.objects.building, model.objects.hospital);
		return $("<select>", {name: "at"}).html($.map(locations, function (node, node_id) {
			var o = $("<option>", {value: node_id, selected: current_node === node_id}).html(node_id);
			return o;
		}));
	},
	edge: function (key, value) {
		return $("<input>", {type: "checkbox", name: "blocked", checked: !value})
	}
}
OBJECT_FIELD_CREATOR["blocked-edge"] = function() {return null;};


var OBJECT_FIELD_SAVER = {
	set: function(object, key, value, create, known) {
		if (object.hasOwnProperty(key)) {
			object[key] = value;
		} else if (object.known && object.known.hasOwnProperty(key)) {
			object.known[key] = value;
		} else if (object.unknown && object.unknown.hasOwnProperty(key)) {
			object.unknown[key].actual = value;
		} else if (create) {
			if (known) {
				object.known[key] = value;
			} else {
				object.unknown = {actual: value};
			}
		} else {
			throw "cannot serialise `" + key + "` " + object;
		}
	},
	at: function(object, key, value) {
		this.set(object, key, [true, value]);
	},
	blocked: function (object, key, value) {
		var known = object.known.edge || object.known["blocked-edge"];
		this.set(object, "edge", !value, true, known);
		this.set(object, "blocked-edge", value, true, known);
	}
};
OBJECT_FIELD_SAVER.available = OBJECT_FIELD_SAVER.set;
OBJECT_FIELD_SAVER.empty = OBJECT_FIELD_SAVER.set;
OBJECT_FIELD_SAVER.alive = OBJECT_FIELD_SAVER.set;
OBJECT_FIELD_SAVER.buried = OBJECT_FIELD_SAVER.set;
OBJECT_FIELD_SAVER.buriedness = OBJECT_FIELD_SAVER.set;
OBJECT_FIELD_SAVER.blockedness = OBJECT_FIELD_SAVER.set;
OBJECT_FIELD_SAVER.distance = OBJECT_FIELD_SAVER.set;


var model = null;


function saveObject() {
	try {
		var data = extractDataFromForm($("#object-data-form")[0]);
		var selected_id = $("#id-selector").val();
		var model_object = findModelObject(selected_id, model);
		saveObjectImpl(data, model_object);
		if (selected_id.contains(" ")) {
			var building_ids = selected_id.split(" ");
			building_ids.reverse();
			var reverse_id = building_ids.join(" ");
			var reverse_model_object = findModelObject(reverse_id, model);
			saveObjectImpl(data, reverse_model_object);
			correctBlockedness(model_object, reverse_model_object);
		}
		drawLayout(model);
		displayObjectData(selected_id);
		
	} catch (err) {
		logError(err);
	}
}

function extractDataFromForm(form) {
	return $.map(form.elements, function (value) {
		if (!value.name || value.name === "id") {
			return null;
		}
		if (value.type === "checkbox") {
			var new_value = value.checked;
		} else if (isFinite(value.value)) {
			var new_value = parseFloat(value.value);
		} else {
			var new_value = value.value;
		}
		return {name: value.name, value: new_value};			
	});
}

function saveObjectImpl(data, model_object) {
	$.each(data, function(_i, item) {
		OBJECT_FIELD_SAVER[item.name](model_object, item.name, item.value);
	});
}

function exportModel() {
	try {
		$("#input-model").val(JSON.stringify(model, null, '    '));
    } catch (err) {
    	logError(err);
    }
}

function displayModel() {
    try {
		model = JSON.parse($("#input-model").val().trim());
		createObjectDataForm(model);
		drawLayout(model);
    } catch (err) {
        logError(err);
    }
}

function displayObjectData(selected_id) {
	if (selected_id === undefined) {
		selected_id = $("#id-selector").val();
	} else {
		$("#id-selector").val(selected_id);
	}
	var objects = createObjects(model);
	var selected = objects.filter(function (obj) {return obj.id === selected_id;})[0];
	var selector_row = $("#object-data").children().first();
	var data_rows = wrapFormElementsInTableRows(createObjectDataFormFields(selected, objects));
	$("#object-data").html($.merge([selector_row], data_rows));	
}

function drawLayout(data) {
	$("#canvas").html(createElements(parseData(data)));
    // hack to force refresh of svg canvas
    $("#canvas-container").html($("#canvas-container").html());
}

function createObjects(data) {
	var objects = $.map(OBJECT_TYPES, function(type) {
		return $.map(data.objects[type], function(value, key) {
			if (value.hasOwnProperty("known")) {
				value = $.extend({}, value.known, extractUnknownActualValues(value.unknown));
			}
			return $.extend({id: key, type: type}, value);
		});
	});
	var edges = $.map(data.graph.edges, function (value, key) {
		var parts = key.split(" ");
		parts.sort();
		var sorted_key = parts.join(" ");
		if (key !== sorted_key) {
			return null;
		}
		return $.extend({id: key, type: "edge"}, value.known, extractUnknownActualValues(value.unknown));
	});
	
	var sorter = function (x, y) {return x.id.localeCompare(y.id);};
	objects.sort(sorter);
	edges.sort(sorter);
	$.merge(objects, edges);
	
	return objects;
}

function createObjectDataForm(data) {
	var objects = createObjects(data);
	var form_inputs = $.merge(
		[createObjectDataFormSelector(objects)],
		createObjectDataFormFields(objects[0], objects)
	);
	
	$("#object-data").html(wrapFormElementsInTableRows(form_inputs));
}

function wrapFormElementsInTableRows(form_inputs) {
	return $.map(form_inputs, function (value) {
		return $("<tr>").html([$("<td>").append(value.attr("name")), $("<td>").html(value)]);
	});
}

function createObjectDataFormSelector(objects) {
	return $("<select>", {name: "id", id: "id-selector", onchange: "displayObjectData();"}).html(
		$.map(objects, function (value) {
			return $("<option>", {value: value.id}).html(value.id);
	}));
}

function createObjectDataFormFields(object, objects) {

	var form_elements = $.map(object, function (value, key) {
		var field_creator = OBJECT_FIELD_CREATOR[key];
		if (field_creator === undefined) {
			field_creator = OBJECT_FIELD_CREATOR.default_;
		}
		return field_creator(key, value, objects);
	});
	form_elements.sort(function (x, y) {x.attr("name").localeCompare(y.attr("name"));});
	
	return form_elements;
}

function parseData(data) {
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
		var value = $.extend({}, value.known, extractUnknownActualValues(value.unknown));
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
	var combined = $.extend({}, edge.known, extractUnknownActualValues(edge.unknown));
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
		width: 40, //this.dimensions.width / (2 * this.width),
		height: 40 //this.dimensions.height / (2 * this.height)
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
		var x = map.getNodeX(value.position.x);
		var y = map.getNodeY(value.position.y);
	
		var e = $("<rect>");
		e.attr("x", x);
		e.attr("y", y);
		e.attr("width", map.node.width);
		e.attr("height", map.node.height);
		e.attr("fill", map.node.colour[value.type]);
		e.attr("onclick", "displayObjectData('"+key+"');");
		elements[key] = e;	
		
		elements[key+"-id"] = createTextElement(key, 
			x + map.node.width / 2, 
			y - map.node.height * 1.5, 
			map);
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
		e.attr("onclick", "displayObjectData('"+key+"');");
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
		node_population[key] = [];
	});
	
	$.each(agents, function (key, value) {		
		var node_pos = nodes[value.node].position;
		var x = map.getNodeX(node_pos.x) + map.node.width + map.agent.radius + node_population[value.node].length * (map.agent.radius * 2 + map.agent.gap);
		var y = map.getNodeY(node_pos.y) + map.node.height + map.agent.radius;
		
		var e = $("<circle>");
		e.attr("cx", x);
		e.attr("cy", y);
		e.attr("r", map.agent.radius);
		e.attr("fill", map.agent.colour[value.type]);
		e.attr("onclick", "displayObjectData('"+key+"');");
		agent_elements[key] = e;
		
		node_population[value.node].push(key);
	});
	
	$.each(node_population, function (key, value) {
		var node_pos = nodes[key].position;
		var x = map.getNodeX(node_pos.x) + map.node.width / 2;
		var y = map.getNodeY(node_pos.y) + map.agent.radius * 3;
		agent_elements[key+"-agents"] = createTextElement(value.join(", "), x, y, map);
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

function extractUnknownActualValues(unknowns) {
	var actuals = {};
	$.each(unknowns, function (key, value) {
		actuals[key] = value.actual;
	});
	return actuals;
}

function findModelObject(object_id, model) {
	var object_sources = [model.objects.medic, model.objects.police, 
		model.objects.civilian, model.objects.hospital, model.objects.building, 
		model.graph.edges];
	var [result] = object_sources.filter(function (value) {
		return value[object_id];
	});
	return result[object_id];
}

function correctBlockedness(edge, reverse_edge) {
	var is_edge = edge.known.edge || (edge.unknown.edge && edge.unknown.edge.actual);
	if (is_edge) {
		// delete blockedness values
		delete edge.known.blockedness;
		delete edge.unknown.blockedness;
		delete reverse_edge.known.blockedness;
		delete reverse_edge.unknown.blockedness;
	} else {
		// add blockness if not there
		if (edge.known["blocked-edge"] && edge.known.blockedness === undefined) {
			// edge-ness is known
			edge.known.blockedness = 0;
			reverse_edge.known.blockedness = 0;
		} else if ((edge.unknown["blocked-edge"] && edge.unknown["blocked-edge"].actual) && edge.unknown.blockedness === undefined) {
			edge.unknown.blockedness = {min: 0, max: 100, actual: 0};
			reverse_edge.unknown.blockedness = {min: 0, max: 100, actual: 0};
		}
	}
}

function logError(err) {
	var p = $("#error-log").empty()
		.append($("<p>").append($("<strong>").text(err.name)).append(" at line: "+err.lineNumber+" of "+err.fileName))
		.append($("<p>").append($("<strong>").text("message: ")).append(err.message));
	p.append($("<p>")
	    .append($("<strong>").text("Stacktrace:"))
	    .append($("<list>")
	        .append($.map(err.stack.split(/\n/), function (item) {
	            return $("<li>").text(item);
	        }))
	));
}
