function createChart() {
	var data = parseData();
	var actions = data[0];
	var colours = data[1];
	drawChart(actions, colours);
}

function parseData() {
	
	var chart_colours = {
		"Move": "#8B0000",
		"Clean": "#FFA500",
		"ExtraClean": "#006400",
		"Plan": "#0000FF",
		"Other": "#000000"
	};
	
	var data = $("#input-data").val().trim();
	
	data = data.replace(/[\[\]]/g, "");
	data = data.split(/\), ?|\)/);
	var actions = [];
	var colours = {};
	for (var index in data) {
		var action = data[index];
		if (action === "") {
			continue;
		}
		var components = action.split(/\(|, ?/);
		var result = createChartElementData(components, chart_colours, colours);
		actions.push(result);
	}
	
	actions.sort(function(x,y) {
		if (x[0] === y[0]) {
			return x[2] - y[2];
		} else if (x[0] === "planner" || y[0] == undefined) {
			return -1;
		} else if (x[0] === undefined || y[0] === "planner") {
			return 1;
		} else {
			return x[0].localeCompare(y[0]);
		}
	});
	
	var chartColourList = [];
	var labels = {};
	
	for (var i in actions) {
		var action = actions[i];
		var label = action[1];
		if (!labels[label]) {
			chartColourList.push(colours[label]);
			labels[label] = true;
		}
	}	
	
	return [actions, chartColourList];
}

function createChartElementData(components, chart_colours, colours) {

	var dict = {};
	for (var i = 1; i < components.length; i++) {
		var key_value_pair = components[i].split("=");
		var value = key_value_pair[1];
		value = value.replace(/'|"/g, "");
		dict[key_value_pair[0]] = value;
	}

	var result = [
		dict["agent"],
		actionLabel(components[0], dict, chart_colours, colours), // action name
		parseFloat(dict["start_time"]) * 1000,
		(parseFloat(dict["start_time"]) + parseFloat(dict["duration"])) * 1000
	];
	return result;
}



function actionLabel(name, components, chart_colours, colours) {
	var label = name;
	
	if (name === "Move") {
		label = "Move "+components["end_node"];
	} else if (name === "Clean" || name == "ExtraClean") {
		label = name + " " + components["room"];
	}
	

	var colour = chart_colours[name];
	if (!colour) {
		colour = chart_colours["Other"];
	}
	colours[label] = colour;

	return label;
}

function drawChart(data, colours) {

  var container = document.getElementById('example3.1');
  var chart = new google.visualization.Timeline(container);

  var dataTable = new google.visualization.DataTable();
  dataTable.addColumn({ type: 'string', id: 'Position' });
  dataTable.addColumn({ type: 'string', id: 'Name' });
  dataTable.addColumn({ type: 'number', id: 'Start' });
  dataTable.addColumn({ type: 'number', id: 'End' });
  dataTable.addRows(data);
  
  var options = { 
  	"colors": colours
  };
  
  chart.draw(dataTable, options);
}
