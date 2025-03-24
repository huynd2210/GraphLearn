import argparse
import os
import re
import json
import networkx as nx
import random


def load_dot_file(dot_file):
    """Load a DOT file into a NetworkX graph."""
    try:
        G = nx.drawing.nx_pydot.read_dot(dot_file)
        return G
    except Exception as e:
        print(f"Error using NetworkX to read DOT file: {e}")
        print("Falling back to manual parsing...")
        
        try:
            # Manual parsing fallback
            G = nx.Graph()
            
            # Read the DOT file with UTF-8 encoding
            with open(dot_file, 'r', encoding='utf-8') as f:
                dot_content = f.read()
            
            # Pattern to match both directed and undirected edges in DOT syntax
            edge_pattern = re.compile(r'\s*"?([^"]+)"?\s*[-][-|>]\s*"?([^"]+)"?')
            
            for line in dot_content.split('\n'):
                line = line.strip()
                # Skip empty lines, comments or brackets
                if not line or line.startswith('//') or line.startswith('#') or line in ['{', '}', 'graph G {']:
                    continue
                
                # Check if it's an edge definition
                match = edge_pattern.match(line)
                if match:
                    source, dest = match.groups()
                    # Remove trailing semicolons if present
                    if dest.endswith(';'):
                        dest = dest[:-1]
                    
                    # Add edge
                    G.add_edge(source, dest)
                elif '--' in line:  # Simpler fallback for edges
                    parts = line.split('--')
                    if len(parts) >= 2:
                        source = parts[0].strip().strip('"')
                        dest = parts[1].strip().strip('"').split(';')[0].strip().strip('"')
                        G.add_edge(source, dest)
            
            return G
        except Exception as e:
            print(f"Error with manual parsing: {e}")
            raise


def find_important_nodes(G, method="degree", top_n=20):
    """
    Find important nodes in the graph for initial display.
    
    Args:
        G: The graph
        method: Method to determine importance ('degree', 'betweenness', 'pagerank')
        top_n: Number of top nodes to return
        
    Returns:
        list of important nodes
    """
    if method == "degree":
        # Use degree centrality
        importance = dict(G.degree())
    elif method == "betweenness":
        # Use betweenness centrality (slower but better for finding bridges)
        try:
            importance = nx.betweenness_centrality(G, k=min(100, len(G)))
        except:
            print("Error computing betweenness centrality. Using degree instead.")
            importance = dict(G.degree())
    elif method == "pagerank":
        # Use PageRank
        try:
            importance = nx.pagerank(G)
        except:
            print("Error computing PageRank. Using degree instead.")
            importance = dict(G.degree())
    else:
        importance = dict(G.degree())
    
    # Sort by importance
    sorted_nodes = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    return [node for node, _ in sorted_nodes[:top_n]]


def prepare_graph_data(G, max_initial_nodes=50):
    """
    Prepare graph data in a format suitable for visualization with vis.js.
    
    Args:
        G: NetworkX graph
        max_initial_nodes: Maximum number of nodes to include in the initial view
        
    Returns:
        dict with nodes and edges in vis.js format
    """
    # Find important nodes for initial display
    important_nodes = find_important_nodes(G, method="degree", top_n=max_initial_nodes)
    
    # Create initial graph from important nodes and their direct connections
    initial_nodes = set(important_nodes)
    for node in important_nodes:
        neighbors = set(G.neighbors(node))
        if len(initial_nodes) + len(neighbors) <= max_initial_nodes * 2:
            initial_nodes.update(neighbors)
        else:
            # Add only some neighbors if there are too many
            neighbors_list = list(neighbors)
            random.shuffle(neighbors_list)
            for neighbor in neighbors_list:
                if len(initial_nodes) >= max_initial_nodes * 2:
                    break
                initial_nodes.add(neighbor)
    
    # Create nodes list for vis.js
    nodes_list = []
    for i, node in enumerate(G.nodes()):
        # Prepare node data
        node_data = {
            "id": str(i),  # Use numeric IDs for vis.js
            "label": str(node),
            "real_id": str(node),  # Store the original node ID
            "value": G.degree(node),  # Size based on degree
            "hidden": node not in initial_nodes  # Initially hide nodes not in the important set
        }
        
        # Style for important nodes
        if node in important_nodes:
            node_data["color"] = {
                "background": "#ff9999",
                "border": "#ff0000"
            }
            node_data["borderWidth"] = 2
        
        nodes_list.append(node_data)
    
    # Create a mapping from original node IDs to vis.js node IDs
    node_id_map = {node: str(i) for i, node in enumerate(G.nodes())}
    
    # Create edges list for vis.js
    edges_list = []
    for i, (u, v) in enumerate(G.edges()):
        # Prepare edge data
        edge_data = {
            "id": str(i),
            "from": node_id_map[u],
            "to": node_id_map[v],
            "hidden": u not in initial_nodes or v not in initial_nodes  # Initially hide edges not connected to important nodes
        }
        edges_list.append(edge_data)
    
    return {
        "nodes": nodes_list,
        "edges": edges_list,
        "node_id_map": node_id_map,
        "important_nodes": [node_id_map[node] for node in important_nodes]
    }


def create_interactive_visualization(G, output_file, max_initial_nodes=50):
    """
    Create an interactive graph visualization where clicking nodes expands their neighborhood.
    
    Args:
        G: NetworkX graph
        output_file: Path to the output HTML file
        max_initial_nodes: Maximum number of nodes to show initially
    """
    # Prepare graph data
    graph_data = prepare_graph_data(G, max_initial_nodes)
    
    # Calculate graph statistics
    stats = {
        "total_nodes": len(G),
        "total_edges": len(G.edges()),
        "avg_degree": sum(dict(G.degree()).values()) / len(G)
    }
    
    # Create HTML file with embedded JavaScript
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Interactive Graph Explorer</title>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style type="text/css">
            body, html {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                height: 100%;
                width: 100%;
                overflow: hidden;
            }
            #network-container {
                width: 100%;
                height: 90vh;
                border: 1px solid #ddd;
                background-color: #f9f9f9;
            }
            #controls {
                padding: 10px;
                background-color: #f0f0f0;
                border-bottom: 1px solid #ddd;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            #search-container {
                display: flex;
                align-items: center;
            }
            #node-search {
                padding: 5px;
                margin-right: 10px;
                width: 200px;
            }
            #search-results {
                position: absolute;
                top: 40px;
                left: 10px;
                width: 300px;
                max-height: 200px;
                overflow-y: auto;
                background: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                display: none;
                z-index: 1000;
            }
            .search-result {
                padding: 8px 12px;
                cursor: pointer;
            }
            .search-result:hover {
                background-color: #f0f0f0;
            }
            #stats {
                margin-right: 20px;
                font-size: 0.9em;
            }
            button {
                padding: 6px 12px;
                margin-left: 10px;
                cursor: pointer;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
            }
            button:hover {
                background-color: #45a049;
            }
            h1 {
                margin: 0;
                font-size: 1.5em;
            }
        </style>
    </head>
    <body>
        <div id="controls">
            <div>
                <h1>Interactive Graph Explorer</h1>
            </div>
            <div id="search-container">
                <input type="text" id="node-search" placeholder="Search nodes...">
                <button id="search-button">Search</button>
                <div id="search-results"></div>
            </div>
            <div id="stats">
                <span>Total Nodes: ${total_nodes}</span> |
                <span>Total Edges: ${total_edges}</span> |
                <span>Avg Degree: ${avg_degree.toFixed(2)}</span>
                <button id="reset-view">Reset View</button>
            </div>
        </div>
        <div id="network-container"></div>
        
        <script type="text/javascript">
            // Graph data
            const nodes = new vis.DataSet(${nodes_json});
            const edges = new vis.DataSet(${edges_json});
            
            // Create a network
            const container = document.getElementById('network-container');
            const data = {
                nodes: nodes,
                edges: edges
            };
            const options = {
                nodes: {
                    shape: 'dot',
                    scaling: {
                        min: 10,
                        max: 30,
                        label: {
                            enabled: true,
                            min: 14,
                            max: 30
                        }
                    },
                    font: {
                        size: 12,
                        face: 'Tahoma'
                    }
                },
                edges: {
                    width: 0.15,
                    color: {
                        color: '#808080',
                        highlight: '#ff0000'
                    },
                    smooth: {
                        type: 'continuous'
                    }
                },
                physics: {
                    stabilization: false,
                    barnesHut: {
                        gravitationalConstant: -80000,
                        springConstant: 0.001,
                        springLength: 200
                    }
                },
                interaction: {
                    tooltipDelay: 200,
                    hideEdgesOnDrag: true,
                    hover: true
                }
            };
            const network = new vis.Network(container, data, options);
            
            // Track expanded nodes
            const expandedNodes = new Set();
            
            // Function to expand a node's neighborhood
            function expandNode(nodeId) {
                if (expandedNodes.has(nodeId)) return;
                
                // Mark node as expanded
                expandedNodes.add(nodeId);
                
                // Get the real node ID
                const nodeData = nodes.get(nodeId);
                const realNodeId = nodeData.real_id;
                
                // Update the node to show it's expanded
                nodes.update({
                    id: nodeId,
                    color: {
                        background: '#aaddff',
                        border: '#0088ff'
                    }
                });
                
                // Find all connected nodes
                const connectedNodes = [];
                const connectedEdges = [];
                
                edges.forEach(edge => {
                    if ((edge.from === nodeId && edge.hidden) || 
                        (edge.to === nodeId && edge.hidden)) {
                        
                        const otherNodeId = edge.from === nodeId ? edge.to : edge.from;
                        
                        // Show this edge
                        edges.update({
                            id: edge.id,
                            hidden: false
                        });
                        
                        // Show the connected node
                        nodes.update({
                            id: otherNodeId,
                            hidden: false
                        });
                        
                        // Add to our list for layout stabilization
                        connectedNodes.push(otherNodeId);
                        connectedEdges.push(edge.id);
                    }
                });
                
                // If new nodes were revealed, adjust the view
                if (connectedNodes.length > 0) {
                    // Apply a local layout stabilization
                    const nodeIds = [nodeId, ...connectedNodes];
                    network.stabilize(nodeIds);
                    
                    // Focus on this neighborhood
                    network.fit({
                        nodes: nodeIds,
                        animation: true
                    });
                }
            }
            
            // Double-click event to expand nodes
            network.on("doubleClick", function(params) {
                if (params.nodes.length > 0) {
                    expandNode(params.nodes[0]);
                }
            });
            
            // Search functionality
            const searchInput = document.getElementById('node-search');
            const searchButton = document.getElementById('search-button');
            const searchResults = document.getElementById('search-results');
            
            function performSearch() {
                const searchTerm = searchInput.value.toLowerCase();
                if (searchTerm.length < 2) {
                    searchResults.style.display = 'none';
                    return;
                }
                
                // Find matching nodes
                const matches = [];
                nodes.forEach(node => {
                    if (node.label.toLowerCase().includes(searchTerm)) {
                        matches.push(node);
                    }
                });
                
                // Display results
                searchResults.innerHTML = '';
                if (matches.length === 0) {
                    searchResults.innerHTML = '<div class="search-result">No matches found</div>';
                } else {
                    matches.slice(0, 10).forEach(node => {
                        const div = document.createElement('div');
                        div.className = 'search-result';
                        div.textContent = node.label;
                        div.onclick = function() {
                            // Focus on this node
                            nodes.update({
                                id: node.id,
                                hidden: false
                            });
                            network.focus(node.id, {
                                scale: 1.5,
                                animation: true
                            });
                            expandNode(node.id);
                            searchResults.style.display = 'none';
                            searchInput.value = node.label;
                        };
                        searchResults.appendChild(div);
                    });
                }
                
                searchResults.style.display = 'block';
            }
            
            searchButton.addEventListener('click', performSearch);
            searchInput.addEventListener('keyup', function(e) {
                if (e.key === 'Enter') {
                    performSearch();
                } else if (searchInput.value.length >= 2) {
                    performSearch();
                } else {
                    searchResults.style.display = 'none';
                }
            });
            
            // Hide search results when clicking outside
            document.addEventListener('click', function(e) {
                if (!searchResults.contains(e.target) && e.target !== searchInput && e.target !== searchButton) {
                    searchResults.style.display = 'none';
                }
            });
            
            // Reset view
            document.getElementById('reset-view').addEventListener('click', function() {
                // Reset to showing only important nodes
                const importantNodes = ${important_nodes_json};
                
                nodes.forEach(node => {
                    const isImportant = importantNodes.includes(node.id);
                    nodes.update({
                        id: node.id,
                        hidden: !isImportant,
                        color: isImportant ? {
                            background: '#ff9999',
                            border: '#ff0000'
                        } : undefined
                    });
                });
                
                edges.forEach(edge => {
                    const fromImportant = importantNodes.includes(edge.from);
                    const toImportant = importantNodes.includes(edge.to);
                    edges.update({
                        id: edge.id,
                        hidden: !(fromImportant && toImportant)
                    });
                });
                
                expandedNodes.clear();
                network.fit();
            });
            
            // Initial layout stabilization
            network.once('stabilizationIterationsDone', function() {
                network.setOptions({ physics: false });
            });
        </script>
    </body>
    </html>
    """
    
    # Replace placeholders with actual data
    html_content = html_template.replace("${total_nodes}", str(stats["total_nodes"]))
    html_content = html_content.replace("${total_edges}", str(stats["total_edges"]))
    html_content = html_content.replace("${avg_degree}", str(stats["avg_degree"]))
    html_content = html_content.replace("${nodes_json}", json.dumps(graph_data["nodes"]))
    html_content = html_content.replace("${edges_json}", json.dumps(graph_data["edges"]))
    html_content = html_content.replace("${important_nodes_json}", json.dumps(graph_data["important_nodes"]))
    
    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Interactive visualization saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Create an interactive expandable graph visualization.")
    parser.add_argument('--dot', type=str, required=True, help='Path to the DOT file.')
    parser.add_argument('--output', type=str, default='interactive_graph.html', help='Path to the output HTML file.')
    parser.add_argument('--initial-nodes', type=int, default=50, help='Maximum number of initial nodes to display.')
    
    args = parser.parse_args()
    
    try:
        # Load the graph
        G = load_dot_file(args.dot)
        print(f"Loaded graph with {len(G)} nodes and {len(G.edges())} edges")
        
        # Create interactive visualization
        create_interactive_visualization(G, args.output, args.initial_nodes)
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main() 