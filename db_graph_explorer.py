import argparse
import os
import re
import json
import networkx as nx
import random
import sqlite3
from flask import Flask, jsonify, request, send_file, render_template_string

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

def preprocess_graph(dot_file, db_file):
    """Load graph from DOT file and store in SQLite database."""
    # Load the graph
    G = load_dot_file(dot_file)
    print(f"Loaded graph with {len(G)} nodes and {len(G.edges())} edges")
    
    # Create database
    if os.path.exists(db_file):
        os.remove(db_file)
    
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS nodes
                 (id TEXT PRIMARY KEY, label TEXT, degree INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS edges
                 (id INTEGER PRIMARY KEY, source TEXT, target TEXT,
                  FOREIGN KEY(source) REFERENCES nodes(id),
                  FOREIGN KEY(target) REFERENCES nodes(id),
                  UNIQUE(source, target))''')
    
    # Insert nodes with batch processing
    batch_size = 1000
    nodes_data = []
    
    print("Processing nodes...")
    for i, node in enumerate(G.nodes()):
        # SQLite doesn't like some special characters in identifiers
        node_id = str(node).replace("'", "''")
        node_label = str(node).replace("'", "''")
        nodes_data.append((node_id, node_label, G.degree(node)))
        
        # Insert batch if it reaches batch_size
        if len(nodes_data) >= batch_size:
            c.executemany("INSERT INTO nodes VALUES (?,?,?)", nodes_data)
            nodes_data = []
            conn.commit()
            print(f"Processed {i+1} nodes...")
    
    # Insert any remaining nodes
    if nodes_data:
        c.executemany("INSERT INTO nodes VALUES (?,?,?)", nodes_data)
        conn.commit()
    
    # Insert edges with batch processing
    print("Processing edges...")
    edges_data = []
    edge_set = set()  # To track already processed edges
    
    for i, (u, v) in enumerate(G.edges()):
        # Process node identifiers
        source_id = str(u).replace("'", "''")
        target_id = str(v).replace("'", "''")
        
        # Ensure we don't add duplicate edges (regardless of direction for undirected graphs)
        edge_pair = tuple(sorted([source_id, target_id]))
        if edge_pair in edge_set:
            continue
            
        edge_set.add(edge_pair)
        edges_data.append((i, source_id, target_id))
        
        # Insert batch if it reaches batch_size
        if len(edges_data) >= batch_size:
            try:
                c.executemany("INSERT OR IGNORE INTO edges VALUES (?,?,?)", edges_data)
                edges_data = []
                conn.commit()
                print(f"Processed {i+1} edges...")
            except sqlite3.IntegrityError as e:
                print(f"Error inserting edges batch: {e}")
                # Continue with next batch
                edges_data = []
    
    # Insert any remaining edges
    if edges_data:
        try:
            c.executemany("INSERT OR IGNORE INTO edges VALUES (?,?,?)", edges_data)
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error inserting final edges batch: {e}")
    
    # Create indices for faster querying
    print("Creating indices...")
    c.execute("CREATE INDEX IF NOT EXISTS idx_source ON edges (source)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_target ON edges (target)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_node_degree ON nodes (degree)")
    
    # Find important nodes
    print("Finding important nodes...")
    important_nodes = find_important_nodes(G, method="degree", top_n=50)
    
    c.execute('''CREATE TABLE IF NOT EXISTS important_nodes
                 (id TEXT PRIMARY KEY,
                  FOREIGN KEY(id) REFERENCES nodes(id))''')
    
    important_nodes_data = [(str(node).replace("'", "''"),) for node in important_nodes]
    c.executemany("INSERT INTO important_nodes VALUES (?)", important_nodes_data)
    
    # Add graph metadata
    c.execute('''CREATE TABLE IF NOT EXISTS graph_stats
                 (key TEXT PRIMARY KEY, value TEXT)''')
    stats = [
        ("total_nodes", str(len(G))),
        ("total_edges", str(len(G.edges()))),
        ("avg_degree", str(sum(dict(G.degree()).values()) / len(G))),
    ]
    c.executemany("INSERT INTO graph_stats VALUES (?,?)", stats)
    
    conn.commit()
    conn.close()
    print(f"Graph data successfully saved to {db_file}")

# Create a Flask app to serve the data
app = Flask(__name__)

@app.route('/')
def index():
    # Get graph stats from database
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute("SELECT key, value FROM graph_stats")
    stats = dict(c.fetchall())
    conn.close()
    
    # HTML template for the interactive visualization
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Database-Backed Graph Explorer</title>
        <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
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
                max-height: 300px;
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
            .loading {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background-color: rgba(255, 255, 255, 0.8);
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                display: none;
                z-index: 1000;
            }
            #node-info {
                position: absolute;
                bottom: 20px;
                right: 20px;
                background-color: white;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                display: none;
                max-width: 300px;
                z-index: 1000;
            }
        </style>
    </head>
    <body>
        <div id="controls">
            <div>
                <h1>Database-Backed Graph Explorer</h1>
            </div>
            <div id="search-container">
                <input type="text" id="node-search" placeholder="Search nodes...">
                <button id="search-button">Search</button>
                <div id="search-results"></div>
            </div>
            <div id="stats">
                <span>Total Nodes: {{ total_nodes }}</span> |
                <span>Total Edges: {{ total_edges }}</span> |
                <span>Avg Degree: {{ avg_degree }}</span>
                <button id="reset-view">Reset View</button>
            </div>
        </div>
        <div id="network-container"></div>
        <div class="loading" id="loading">Loading data...</div>
        <div id="node-info"></div>
        
        <script type="text/javascript">
            // Initialize empty network
            const nodes = new vis.DataSet([]);
            const edges = new vis.DataSet([]);
            const expandedNodes = new Set();
            
            // Create a network
            const container = document.getElementById('network-container');
            const loading = document.getElementById('loading');
            const nodeInfo = document.getElementById('node-info');
            
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
            
            // Function to expand a node's neighborhood
            function expandNode(nodeId) {
                if (expandedNodes.has(nodeId)) return;
                
                // Mark node as expanded
                expandedNodes.add(nodeId);
                
                // Update the node to show it's expanded
                nodes.update({
                    id: nodeId,
                    color: {
                        background: '#aaddff',
                        border: '#0088ff'
                    }
                });
                
                // Show loading indicator
                loading.style.display = 'block';
                
                // Load neighborhood from server
                $.getJSON(`/api/expand/${encodeURIComponent(nodeId)}`, function(data) {
                    // Add new nodes that don't already exist
                    const existingNodeIds = new Set(nodes.getIds().map(id => id.toString()));
                    const newNodes = data.nodes.filter(n => !existingNodeIds.has(n.id.toString()));
                    
                    if (newNodes.length > 0) {
                        nodes.add(newNodes.map(node => ({
                            id: node.id,
                            label: node.label,
                            value: node.degree
                        })));
                    }
                    
                    // Add new edges that don't already exist
                    const existingEdgeIds = new Set(edges.getIds().map(id => id.toString()));
                    const newEdges = data.edges.filter(e => !existingEdgeIds.has(e.id.toString()));
                    
                    if (newEdges.length > 0) {
                        edges.add(newEdges.map(edge => ({
                            id: edge.id,
                            from: edge.source,
                            to: edge.target
                        })));
                    }
                    
                    // Apply physics to layout new nodes
                    network.stabilize(50);
                    
                    // Hide loading indicator
                    loading.style.display = 'none';
                })
                .fail(function() {
                    // Hide loading indicator on error
                    loading.style.display = 'none';
                    alert("Error loading node data");
                    // Remove from expanded set to allow retry
                    expandedNodes.delete(nodeId);
                });
            }
            
            // Double-click event to expand nodes
            network.on("doubleClick", function(params) {
                if (params.nodes.length > 0) {
                    expandNode(params.nodes[0]);
                }
            });
            
            // Show node info on select
            network.on("selectNode", function(params) {
                if (params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    const nodeData = nodes.get(nodeId);
                    
                    // Get node info from server
                    $.getJSON(`/api/node/${encodeURIComponent(nodeId)}`, function(data) {
                        // Create Wikipedia URL by replacing spaces with underscores
                        const wikiTitle = data.label.replace(/ /g, '_');
                        const wikiUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
                        
                        nodeInfo.innerHTML = `
                            <h3>${data.label}</h3>
                            <p>Degree: ${data.degree}</p>
                            <p>Connected to ${data.neighbors} nodes</p>
                            <p><a href="#" onclick="expandNode('${nodeId}'); return false;">Expand this node</a></p>
                            <p><a href="${wikiUrl}" target="_blank">View Wikipedia page</a></p>
                        `;
                        nodeInfo.style.display = 'block';
                    });
                } else {
                    nodeInfo.style.display = 'none';
                }
            });
            
            network.on("deselectNode", function() {
                nodeInfo.style.display = 'none';
            });
            
            // Search functionality
            const searchInput = document.getElementById('node-search');
            const searchButton = document.getElementById('search-button');
            const searchResults = document.getElementById('search-results');
            
            function performSearch() {
                const searchTerm = searchInput.value.trim();
                if (searchTerm.length < 2) {
                    searchResults.style.display = 'none';
                    return;
                }
                
                searchResults.innerHTML = '<div class="search-result">Searching...</div>';
                searchResults.style.display = 'block';
                
                // Send search request to server
                $.getJSON(`/api/search?q=${encodeURIComponent(searchTerm)}`, function(data) {
                    searchResults.innerHTML = '';
                    
                    if (data.length === 0) {
                        searchResults.innerHTML = '<div class="search-result">No matches found</div>';
                    } else {
                        data.forEach(node => {
                            const div = document.createElement('div');
                            div.className = 'search-result';
                            div.textContent = node.label;
                            div.onclick = function() {
                                // Check if node is already in the network
                                const existingIds = new Set(nodes.getIds().map(id => id.toString()));
                                
                                if (!existingIds.has(node.id.toString())) {
                                    // Add node to network
                                    nodes.add({
                                        id: node.id,
                                        label: node.label,
                                        value: node.degree,
                                        color: {
                                            background: '#ddeeff',
                                            border: '#4477aa'
                                        }
                                    });
                                }
                                
                                // Focus on this node
                                network.focus(node.id, {
                                    scale: 1.5,
                                    animation: true
                                });
                                
                                // Select the node
                                network.selectNodes([node.id]);
                                
                                // Hide search results
                                searchResults.style.display = 'none';
                                searchInput.value = node.label;
                            };
                            searchResults.appendChild(div);
                        });
                    }
                })
                .fail(function() {
                    searchResults.innerHTML = '<div class="search-result">Error performing search</div>';
                });
            }
            
            searchButton.addEventListener('click', performSearch);
            searchInput.addEventListener('keyup', function(e) {
                if (e.key === 'Enter') {
                    performSearch();
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
                // Show loading indicator
                loading.style.display = 'block';
                
                // Clear current data
                nodes.clear();
                edges.clear();
                expandedNodes.clear();
                
                // Load initial data
                $.getJSON('/api/initial', function(data) {
                    if (data.nodes && data.nodes.length > 0) {
                        nodes.add(data.nodes.map(node => ({
                            id: node.id,
                            label: node.label,
                            value: node.degree,
                            color: {
                                background: '#ff9999',
                                border: '#ff0000'
                            }
                        })));
                    }
                    
                    if (data.edges && data.edges.length > 0) {
                        edges.add(data.edges.map(edge => ({
                            id: edge.id,
                            from: edge.source,
                            to: edge.target
                        })));
                    }
                    
                    // Apply physics and fit view
                    network.stabilize();
                    network.fit();
                    
                    // Hide loading indicator
                    loading.style.display = 'none';
                })
                .fail(function() {
                    loading.style.display = 'none';
                    alert("Error resetting view");
                });
            });
            
            // Load initial data
            loading.style.display = 'block';
            $.getJSON('/api/initial', function(data) {
                if (data.nodes && data.nodes.length > 0) {
                    nodes.add(data.nodes.map(node => ({
                        id: node.id,
                        label: node.label,
                        value: node.degree,
                        color: {
                            background: '#ff9999',
                            border: '#ff0000'
                        }
                    })));
                }
                
                if (data.edges && data.edges.length > 0) {
                    edges.add(data.edges.map(edge => ({
                        id: edge.id,
                        from: edge.source,
                        to: edge.target
                    })));
                }
                
                // Apply physics and fit view
                network.stabilize();
                network.fit();
                
                // Hide loading indicator
                loading.style.display = 'none';
            })
            .fail(function() {
                loading.style.display = 'none';
                alert("Error loading initial data");
            });
            
            // Initial layout stabilization
            network.once('stabilizationIterationsDone', function() {
                network.setOptions({ physics: false });
            });
        </script>
    </body>
    </html>
    '''
    
    # Render the template with graph stats
    return render_template_string(html, 
                                total_nodes=stats.get('total_nodes', 'N/A'),
                                total_edges=stats.get('total_edges', 'N/A'),
                                avg_degree=round(float(stats.get('avg_degree', 0)), 2))

@app.route('/api/initial')
def get_initial_data():
    """Get initial graph data (important nodes and their edges)."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get important nodes
    c.execute("""
        SELECT nodes.* FROM nodes 
        JOIN important_nodes ON nodes.id = important_nodes.id
    """)
    important_nodes = [dict(row) for row in c.fetchall()]
    
    # Get edges between important nodes
    node_ids = [node['id'] for node in important_nodes]
    if node_ids:
        placeholders = ','.join(['?'] * len(node_ids))
        c.execute(f"""
            SELECT DISTINCT edges.* FROM edges 
            WHERE source IN ({placeholders}) AND target IN ({placeholders})
        """, node_ids + node_ids)
        edges = [dict(row) for row in c.fetchall()]
    else:
        edges = []
    
    conn.close()
    return jsonify({'nodes': important_nodes, 'edges': edges})

@app.route('/api/expand/<node_id>')
def expand_node(node_id):
    """Get the neighbors of a node and the edges connecting them."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get neighbors (nodes connected by edges)
    c.execute("""
        SELECT DISTINCT nodes.* FROM nodes
        JOIN edges ON nodes.id = edges.target OR nodes.id = edges.source
        WHERE edges.source = ? OR edges.target = ?
    """, (node_id, node_id))
    neighbors = [dict(row) for row in c.fetchall()]
    
    # Get edges connecting to neighbors
    c.execute("""
        SELECT DISTINCT * FROM edges
        WHERE source = ? OR target = ?
    """, (node_id, node_id))
    edges = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return jsonify({'nodes': neighbors, 'edges': edges})

@app.route('/api/node/<node_id>')
def get_node_info(node_id):
    """Get detailed information about a node."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get node info
    c.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
    node = dict(c.fetchone() or {})
    
    # Get number of neighbors
    c.execute("""
        SELECT COUNT(DISTINCT CASE WHEN source = ? THEN target ELSE source END) as neighbor_count
        FROM edges
        WHERE source = ? OR target = ?
    """, (node_id, node_id, node_id))
    result = c.fetchone()
    neighbors = result['neighbor_count'] if result else 0
    
    conn.close()
    node['neighbors'] = neighbors
    return jsonify(node)

@app.route('/api/search')
def search_nodes():
    """Search for nodes by label."""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])
    
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Search for nodes matching the query
    c.execute("""
        SELECT DISTINCT * FROM nodes
        WHERE label LIKE ?
        ORDER BY degree DESC
        LIMIT 10
    """, (f'%{query}%',))
    
    nodes = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(nodes)

def create_html_file(output_file):
    """Create a standalone HTML file for offline use."""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Offline Graph Explorer</title>
        <script>
            // Redirect to the Flask server
            window.location.href = "http://localhost:5000/";
        </script>
    </head>
    <body>
        <h1>Redirecting to Graph Explorer...</h1>
        <p>If you are not redirected automatically, please start the server with:</p>
        <pre>python db_graph_explorer.py --db graph.db</pre>
        <p>Then click <a href="http://localhost:5000/">here</a> to open the explorer.</p>
    </body>
    </html>
    '''
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML redirect file saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Create a database-backed graph explorer")
    parser.add_argument('--dot', type=str, help='Path to the DOT file for preprocessing')
    parser.add_argument('--db', type=str, default='graph.db', help='Path to the SQLite database')
    parser.add_argument('--html', type=str, default='graph_explorer.html', help='Output HTML file')
    parser.add_argument('--port', type=int, default=5000, help='Port for the server')
    parser.add_argument('--preprocess-only', action='store_true', help='Only preprocess, don\'t start server')
    args = parser.parse_args()
    
    if args.dot:
        # Preprocess and store graph in database
        preprocess_graph(args.dot, args.db)
        create_html_file(args.html)
    
    if not args.preprocess_only:
        # Configure and start Flask server
        app.config['DATABASE'] = args.db
        print(f"Starting server on http://localhost:{args.port}")
        app.run(debug=True, port=args.port, host='0.0.0.0')

if __name__ == '__main__':
    main() 