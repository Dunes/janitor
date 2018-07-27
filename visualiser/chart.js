function createChart($, google) {
    try {
        var data = parseData($);
        var actions = data[0];
        var colours = data[1];
        drawChart(actions, colours, google);
    } catch (err) {
        $("#error-log").html(err);
    }
}

function parseData($) {

    var chart_colours = {
    	// generic actions
        "Move": "#8B0000",
        "Plan": "#0000FF",
        "LocalPlan": "#0000FF",
        "Other": "#000000",
        // partial generic actions
 		"Partial Move": "#ae4d4d",
        "Partial Plan": "#8282ff",
 
        // janitor actions
        "Clean": "#FFA500",
        "ExtraClean": "#006400",
        "ExtraCleanPart": "#4d934d",
        "ExtraCleanAssist": "#4d934d",
		// partial janitor actions
        "Partial Clean": "#ffc04d",
        "Partial ExtraClean": "#4d934d",
        "Partial ExtraCleanPart": "#9ccb9c",
        "Partial ExtraCleanAssist": "#9ccb9c",

        // roborescue actions
        "Unblock": "#FFA500",
        "Rescue": "#006400",
		// partial roborescue actions
        "Partial Unblock": "#ffc04d",
        "Partial Rescue": "#4d934d",

        // truck actions
        "Drive": "#8B0000",
        "Sail": "#8B0000",
        "Load": "#FFA500",
        "Unload": "#006400",
        "DeliverOntime": "#8282ff",
        "DeliverAnytime": "#8282ff",
        "DeliverMultiple": "#8282ff",
        // partial generic actions
 		"Partial Drive": "#ae4d4d",
        "Partial Sail": "#ae4d4d",
    };

    var data = $("#input-data").val().trim();
    var is_json = true;
    try {
        data = $.parseJSON(data);
    } catch (err) {
        is_json = false;
    }

    if (is_json) {
        var d = data;
        if (data instanceof Object && data.execution !== undefined) {
            d = data.execution;
        }
        var result = actionsFromJson(d, chart_colours);
    } else {
        var result = actionsFromPython(data, chart_colours);
    }
    var actions = result.actions;
    var colours = result.colours;

    actions.sort(function(x, y) {
            if (x[0] === y[0]) {
                return x[2] - y[2];
            } else if (x[0] === "planner" || y[0] === undefined) {
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

function createChartElementDataFromPython(components, chart_colours, colours) {

    var dict = {};
    for (var i = 1; i < components.length; i++) {
        var key_value_pair = components[i].split("=");
        var value = key_value_pair[1];
        value = value.replace(/'|"/g, "");
        dict[key_value_pair[0]] = value;
    }

    var result = [];
    var agents = getAgents(dict);
    for (var j in agents) {
        result.push([
                agents[j],
                actionLabel(components[0], dict, chart_colours, colours, dict.partial === "True"), // action name
                secondsToMillis(dict.start_time),
                secondsToMillis(dict.start_time) + secondsToMillis(dict.duration)
            ]);
    }
    return result;
}


function actionLabel(name, components, chart_colours, colours, partial) {
    var label = name;

    if (["Move", "Drive", "Sail"].indexOf(name) != -1) {
        label = name + " " + components.end_node;
    } else if (name === "Clean" || name === "ExtraClean") {
        label = name + " " + components.room;
    } else if (name === "ExtraCleanPart") {
        label = "ExtraClean " + components.room;
    } else if (name === "Rescue") {
    	label = "Rescue " + components.target
    } else if (name === "Unblock") {
    	label = "Unblock " + components.end_node
    } else if (name === "ExtraCleanAssist") {
        label = "ExtraCleanAssist " + components.room;
    } else if (["Load", "Unload"].indexOf(name) != -1 && "package" in components) {
        label = name + " " + components.package;
    } else if (["DeliverOntime", "DeliverAnytime"].indexOf(name) != -1) {
        label = name + " " + components.package;
    } else if (name === "DeliverMultiple") {
        label = "DeliverMultiple @ " + components.location;
    }


    if (partial) {
        name = "Partial " + name;
        label = "Partial " + label;
    }

    var colour = chart_colours[name];
    if (!colour) {
        colour = chart_colours.Other;
    }
    colours[label] = colour;

    return label;
}

function drawChart(data, colours, google) {

    var container = document.getElementById('example3.1');
    var chart = new google.visualization.Timeline(container);

    var dataTable = new google.visualization.DataTable();
    dataTable.addColumn({
            type: 'string',
            id: 'Position'
        });
    dataTable.addColumn({
            type: 'string',
            id: 'Name'
        });
    dataTable.addColumn({
            type: 'number',
            id: 'Start'
        });
    dataTable.addColumn({
            type: 'number',
            id: 'End'
        });
    dataTable.addRows(data);

    var options = {
        "colors": colours
    };

    chart.draw(dataTable, options);
}

function secondsToMillis(value) {
    var seconds = parseFloat(value);
    var millis = Math.round(seconds * 1000);
    return millis;
}

function getAgents(obj) {
    if (obj.agent) {
        return [obj.agent];
    } else if (obj.agent0) {
        return [obj.agent0, obj.agent1];
    } else {
        throw "Object does not have agents";
    }
}

function actionsFromJson(data, chart_colours) {
    var actions = [];
    var colours = {};
    for (var index in data) {
        var action = data[index];
        var result = createChartElementDataFromJson(action, chart_colours, colours);
        Array.prototype.push.apply(actions, result); // extend actions by result
    }
    return {"actions": actions, "colours": colours};
}

function createChartElementDataFromJson(action, chart_colours, colours) {
    var result = [];
    var agents = getAgents(action);
    for (var j in agents) {
        result.push([
                agents[j],
                actionLabel(action.type, action, chart_colours, colours, action.partial), // action name
                secondsToMillis(action.start_time),
                secondsToMillis(action.start_time) + secondsToMillis(action.duration)
            ]);
    }
    return result;
}

function actionsFromPython(data, chart_colours) {
    data = data.replace(/[\[\]]/g, "");
    data = data.split(/\), ?|\)/);
    var actions = [];
    var partial = [];

    var colours = {};
    for (var index in data) {
        var action = data[index];
        if (action === "") {
            continue;
        }
        var components = action.split(/\(|, ?/);
        var result = createChartElementDataFromPython(components, chart_colours, colours);
        Array.prototype.push.apply(actions, result); // extend actions by result
    }
    return {"actions": actions, "colours": colours};
}
