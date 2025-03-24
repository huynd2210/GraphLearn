import argparse
import os
import re
import json
import networkx as nx
import plotly.graph_objects as go
import numpy as np
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


def get_node_colors_by_type(G, center_node=None, distance_map=None):
    """Assign colors to nodes based on their type or distance from center."""
    node_colors = {}
    
    if center_node is not None and distance_map is not None:
        # Color by distance from center node
        max_distance = max(distance_map.values()) if distance_map else 0
        for node in G.nodes():
            if node == center_node:
                # Center node in red
                node_colors[node] = 1.0  # Will map to red
            elif node in distance_map:
                # Nodes in the path colored by distance (normalized to [0, 0.8])
                dist = distance_map[node]
                node_colors[node] = 0.2 + 0.6 * (max_distance - dist) / max_distance if max_distance > 0 else 0.5
            else:
                # Nodes not in path in light gray
                node_colors[node] = 0
    else:
        # Default coloring by degree
        degrees = dict(G.degree())
        max_degree = max(degrees.values()) if degrees else 1
        for node, degree in degrees.items():
            node_colors[node] = degree / max_degree
            
    return node_colors


def get_node_neighborhood(G, center_node, max_distance=1, max_nodes=100):
    """
    Get a subgraph centered on the given node with neighbors up to max_distance away.
    
    Args:
        G: The full graph
        center_node: The node to center the neighborhood on
        max_distance: Maximum number of edges from center node
        max_nodes: Maximum number of nodes to include
        
    Returns:
        subgraph: NetworkX graph with the neighborhood
        distance_map: Dictionary mapping nodes to their distance from center
    """
    # Check if center_node exists in the graph
    if center_node not in G.nodes():
        print(f"Warning: Node '{center_node}' not found in graph. Selecting a random node.")
        center_node = random.choice(list(G.nodes()))
    
    # Initialize with center node
    nodes_to_include = {center_node}
    distance_map = {center_node: 0}
    
    # BFS to find nodes within max_distance
    current_distance = 0
    frontier = {center_node}
    
    while current_distance < max_distance and len(nodes_to_include) < max_nodes:
        current_distance += 1
        next_frontier = set()
        
        for node in frontier:
            neighbors = set(G.neighbors(node))
            # Remove already included nodes
            neighbors -= nodes_to_include
            
            # Add the new neighbors with their distance
            for neighbor in neighbors:
                if len(nodes_to_include) >= max_nodes:
                    break
                next_frontier.add(neighbor)
                nodes_to_include.add(neighbor)
                distance_map[neighbor] = current_distance
        
        frontier = next_frontier
        if not frontier:
            break
    
    # Create the subgraph
    subgraph = G.subgraph(nodes_to_include)
    return subgraph, distance_map


def find_important_nodes(G, method="degree", top_n=20):
    """
    Find important nodes in the graph for navigation.
    
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


def visualize_graph_page(G, full_graph, center_node=None, output_dir='graph_pages', 
                        page_number=1, max_distance=1, max_nodes=100,
                        layout="fruchterman_reingold", node_size=15, edge_width=1,
                        colorscale='Viridis', include_neighbors=True):
    """
    Create a visualization of a subgraph centered on the given node.
    
    Args:
        G: The full graph
        center_node: The node to center the visualization on
        output_dir: Directory to save the output files
        page_number: Page number for this visualization
        max_distance: Maximum distance from center node to include
        max_nodes: Maximum number of nodes to include
        layout: Layout algorithm to use
        node_size: Base size of nodes
        edge_width: Width of edges
        colorscale: Colorscale for node colors
        include_neighbors: Whether to include a list of neighbor nodes for navigation
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # If no center node is specified, choose a high-degree node
    if center_node is None:
        degrees = dict(G.degree())
        center_node = max(degrees.items(), key=lambda x: x[1])[0]
    
    # Get the neighborhood subgraph
    if include_neighbors:
        subgraph, distance_map = get_node_neighborhood(G, center_node, max_distance, max_nodes)
    else:
        subgraph = G
        distance_map = {node: 0 for node in G.nodes()}
        distance_map[center_node] = 0
    
    # Find the next set of potential neighbors for navigation
    next_neighbors = set()
    for node in subgraph.nodes():
        # Get neighbors from the full graph that aren't in the current subgraph
        neighbors = set(full_graph.neighbors(node))
        neighbors -= set(subgraph.nodes())
        next_neighbors.update(neighbors)
    
    # Find important next neighbors to feature in navigation
    important_next = find_important_nodes(full_graph.subgraph(next_neighbors), method="degree", top_n=10)
    
    # Compute layout
    if layout == "fruchterman_reingold":
        pos = nx.fruchterman_reingold_layout(subgraph, seed=42)
    elif layout == "kamada_kawai":
        pos = nx.kamada_kawai_layout(subgraph)
    elif layout == "circular":
        pos = nx.circular_layout(subgraph)
    elif layout == "shell":
        pos = nx.shell_layout(subgraph)
    elif layout == "spring":
        pos = nx.spring_layout(subgraph, seed=42)
    else:
        pos = nx.spring_layout(subgraph, seed=42)
    
    # Extract node positions
    x_nodes = [pos[node][0] for node in subgraph.nodes()]
    y_nodes = [pos[node][1] for node in subgraph.nodes()]
    
    # Get node colors
    node_colors = get_node_colors_by_type(subgraph, center_node, distance_map)
    node_colors_list = [node_colors[node] for node in subgraph.nodes()]
    
    # Scale node sizes by distance from center
    node_sizes = []
    for node in subgraph.nodes():
        if node == center_node:
            # Center node is larger
            node_sizes.append(node_size * 2)
        elif node in distance_map:
            # Size decreases with distance
            dist = distance_map[node]
            node_sizes.append(node_size * (1 + 0.5 * (max_distance - dist) / max_distance if max_distance > 0 else 1))
        else:
            node_sizes.append(node_size)
    
    # Create node trace
    node_trace = go.Scatter(
        x=x_nodes,
        y=y_nodes,
        mode='markers+text',
        text=[str(node) for node in subgraph.nodes()],
        textposition="top center",
        textfont=dict(size=10, color='black'),
        hoverinfo='text',
        marker=dict(
            size=node_sizes,
            color=node_colors_list,
            colorscale=colorscale,
            opacity=0.8,
            line=dict(width=1, color='black')
        )
    )
    
    # Create edge traces
    edge_traces = []
    for edge in subgraph.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        
        # Thicker edges for edges connected to center node
        if edge[0] == center_node or edge[1] == center_node:
            width = edge_width * 2
            color = 'rgba(180, 0, 0, 0.7)'  # Red for center edges
        else:
            width = edge_width
            color = 'rgba(150, 150, 150, 0.5)'  # Gray for other edges
        
        edge_trace = go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(width=width, color=color),
            hoverinfo='none'
        )
        
        edge_traces.append(edge_trace)
    
    # Create navigation links as annotations
    annotations = []
    
    # Create navigation to next nodes
    nav_links_html = '<div style="margin-top: 20px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
    nav_links_html += f'<h3>Page {page_number} - Centered on: {center_node}</h3>'
    nav_links_html += f'<p>Showing {len(subgraph)} nodes out of {len(G)} total nodes ({len(subgraph)/len(G)*100:.1f}%).</p>'
    
    # Navigation to important next nodes
    if important_next:
        nav_links_html += '<h4>Navigate to connected nodes:</h4><ul>'
        for i, node in enumerate(important_next[:10]):  # Limit to 10 navigation options
            next_page = page_number + i + 1
            nav_links_html += f'<li><a href="page_{next_page}.html" target="_self">{node}</a></li>'
        nav_links_html += '</ul>'
    
    # Add a link to go back to the overview
    nav_links_html += '<p><a href="index.html" target="_self">Back to Overview</a></p>'
    nav_links_html += '</div>'
    
    # Create figure
    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            title=f'Graph Explorer - Page {page_number} - Centered on: {center_node}',
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=annotations,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            width=1000,
            height=800
        )
    )
    
    # Save as HTML file
    output_file = os.path.join(output_dir, f'page_{page_number}.html')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        html_content = fig.to_html(full_html=True, include_plotlyjs='cdn')
        # Insert navigation links before the closing body tag
        html_content = html_content.replace('</body>', f'{nav_links_html}</body>')
        f.write(html_content)
    
    print(f"Page {page_number} saved to {output_file}")
    
    # Return important nodes for continuing navigation
    return important_next


def create_index_page(G, output_dir, important_nodes, max_pages=20):
    """Create an index page with links to the most important nodes in the graph."""
    os.makedirs(output_dir, exist_ok=True)
    
    # HTML template for the index page
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Graph Explorer - Index</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            h1, h2, h3 {{ color: #333; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .stats {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .nav-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }}
            .nav-item {{ padding: 10px; background-color: #e9f7fe; border-radius: 5px; text-align: center; }}
            .nav-item a {{ text-decoration: none; color: #0066cc; }}
            .nav-item a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Graph Explorer</h1>
            
            <div class="stats">
                <h2>Graph Statistics</h2>
                <p>Total Nodes: {len(G)}</p>
                <p>Total Edges: {len(G.edges())}</p>
                <p>Average Degree: {sum(dict(G.degree()).values()) / len(G):.2f}</p>
            </div>
            
            <h2>Select a Starting Node</h2>
            <p>Click on a node to explore its neighborhood:</p>
            
            <div class="nav-grid">
    """
    
    # Add links to important nodes
    for i, node in enumerate(important_nodes[:max_pages]):
        html += f'<div class="nav-item"><a href="page_{i+1}.html">{node}</a></div>\n'
    
    html += """
            </div>
        </div>
    </body>
    </html>
    """
    
    # Write the index page
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Index page saved to {os.path.join(output_dir, 'index.html')}")


def create_graph_explorer(dot_file, output_dir='graph_explorer', max_pages=20, max_distance=1, 
                        max_nodes_per_page=50, layout="fruchterman_reingold", 
                        colorscale='Viridis'):
    """
    Create a multi-page graph explorer for a large graph.
    
    Args:
        dot_file: Path to the DOT file
        output_dir: Directory to save the output files
        max_pages: Maximum number of pages to create
        max_distance: Maximum distance from center node in each page
        max_nodes_per_page: Maximum number of nodes per page
        layout: Layout algorithm to use
        colorscale: Colorscale for node colors
    """
    # Load the graph
    G = load_dot_file(dot_file)
    print(f"Loaded graph with {len(G)} nodes and {len(G.edges())} edges")
    
    # Find important nodes for navigation
    important_nodes = find_important_nodes(G, method="degree", top_n=max_pages)
    
    # Create the index page
    create_index_page(G, output_dir, important_nodes, max_pages)
    
    # Create a page for each important node
    next_nodes = []
    for i, node in enumerate(important_nodes[:max_pages]):
        page_number = i + 1
        next_page_nodes = visualize_graph_page(
            G, G, center_node=node, output_dir=output_dir, 
            page_number=page_number, max_distance=max_distance, 
            max_nodes=max_nodes_per_page, layout=layout,
            colorscale=colorscale
        )
        next_nodes.extend(next_page_nodes)
    
    print(f"Created {min(max_pages, len(important_nodes))} pages in {output_dir}")
    print(f"Open {os.path.join(output_dir, 'index.html')} in your browser to start exploring")


def main():
    parser = argparse.ArgumentParser(description="Create a multi-page graph explorer for large graphs.")
    parser.add_argument('--dot', type=str, required=True, help='Path to the DOT file.')
    parser.add_argument('--output-dir', type=str, default='graph_explorer', help='Directory to save the output files.')
    parser.add_argument('--max-pages', type=int, default=20, help='Maximum number of pages to create.')
    parser.add_argument('--max-distance', type=int, default=1, help='Maximum distance from center node in each page.')
    parser.add_argument('--max-nodes-per-page', type=int, default=50, help='Maximum number of nodes per page.')
    parser.add_argument('--layout', type=str, default='fruchterman_reingold', 
                       choices=['fruchterman_reingold', 'kamada_kawai', 'circular', 'shell', 'spring'],
                       help='Layout algorithm to use.')
    parser.add_argument('--colorscale', type=str, default='Viridis', 
                       choices=['Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis', 'Rainbow', 'Blues', 'Reds', 'Greens'],
                       help='Colorscale for node colors.')
    
    args = parser.parse_args()
    
    try:
        create_graph_explorer(
            args.dot,
            output_dir=args.output_dir,
            max_pages=args.max_pages,
            max_distance=args.max_distance,
            max_nodes_per_page=args.max_nodes_per_page,
            layout=args.layout,
            colorscale=args.colorscale
        )
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main() 