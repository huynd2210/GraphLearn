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


def select_nodes(G, max_nodes=1000, selection_method="degree"):
    """
    Select nodes from the graph if it has too many nodes.
    
    Args:
        G: NetworkX graph
        max_nodes: Maximum number of nodes to visualize
        selection_method: Method to select nodes ('degree', 'random', 'connected')
    
    Returns:
        Subgraph with selected nodes
    """
    if len(G) <= max_nodes:
        return G
    
    print(f"Graph has {len(G)} nodes, which is more than the maximum of {max_nodes}.")
    print(f"Selecting {max_nodes} nodes using method: {selection_method}")
    
    if selection_method == "degree":
        # Select nodes with highest degrees
        degrees = dict(G.degree())
        sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
        nodes_to_keep = [node for node, _ in sorted_nodes]
        return G.subgraph(nodes_to_keep)
    
    elif selection_method == "random":
        # Randomly select nodes
        nodes_to_keep = random.sample(list(G.nodes()), max_nodes)
        return G.subgraph(nodes_to_keep)
    
    elif selection_method == "connected":
        # Select nodes that form a connected component
        components = list(nx.connected_components(G))
        largest_component = max(components, key=len)
        
        if len(largest_component) <= max_nodes:
            return G.subgraph(largest_component)
        else:
            # If the largest component is still too large, take a subset
            nodes_to_keep = list(largest_component)[:max_nodes]
            return G.subgraph(nodes_to_keep)
    
    else:
        print(f"Unknown selection method: {selection_method}. Using degree-based selection.")
        degrees = dict(G.degree())
        sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
        nodes_to_keep = [node for node, _ in sorted_nodes]
        return G.subgraph(nodes_to_keep)


def get_node_colors_by_degree(G, colorscale='Viridis'):
    """Assign colors to nodes based on their degree."""
    # Get node degrees
    degrees = dict(G.degree())
    
    # Normalize degrees to [0, 1] for color mapping
    if len(degrees) > 1:
        min_degree = min(degrees.values())
        max_degree = max(degrees.values())
        norm = lambda d: (d - min_degree) / (max_degree - min_degree) if max_degree > min_degree else 0.5
    else:
        norm = lambda d: 0.5
    
    node_colors = {node: norm(deg) for node, deg in degrees.items()}
    return node_colors


def visualize_with_plotly(G, output_file, layout="fruchterman_reingold", 
                         node_size=10, node_opacity=0.8, edge_width=1, 
                         max_nodes=1000, selection_method="degree",
                         colorscale='Viridis', width=1000, height=800,
                         scale_node_size_by_degree=True):
    """
    Create an interactive graph visualization using Plotly.
    
    Args:
        G: NetworkX graph
        output_file: Path to save the HTML file
        layout: Layout algorithm ('fruchterman_reingold', 'kamada_kawai', etc.)
        node_size: Base size of nodes
        node_opacity: Opacity of nodes (0-1)
        edge_width: Width of edges
        max_nodes: Maximum number of nodes to visualize
        selection_method: Method to select nodes if there are too many
        colorscale: Colorscale for node colors
        width: Width of the plot in pixels
        height: Height of the plot in pixels
        scale_node_size_by_degree: Whether to scale node sizes by their degrees
    """
    # Select subset of nodes if the graph is too large
    if len(G) > max_nodes:
        G = select_nodes(G, max_nodes, selection_method)
    
    # Compute node positions
    if layout == "fruchterman_reingold":
        pos = nx.fruchterman_reingold_layout(G, seed=42)
    elif layout == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    elif layout == "circular":
        pos = nx.circular_layout(G)
    elif layout == "shell":
        pos = nx.shell_layout(G)
    elif layout == "spring":
        pos = nx.spring_layout(G, seed=42)
    elif layout == "spectral":
        pos = nx.spectral_layout(G)
    elif layout == "random":
        pos = nx.random_layout(G)
    else:
        pos = nx.fruchterman_reingold_layout(G, seed=42)
    
    # Extract node positions
    x_nodes = [pos[node][0] for node in G.nodes()]
    y_nodes = [pos[node][1] for node in G.nodes()]
    
    # Get node colors based on degree
    node_colors = get_node_colors_by_degree(G, colorscale)
    node_colors_list = [node_colors[node] for node in G.nodes()]
    
    # Scale node sizes by degree if requested
    if scale_node_size_by_degree:
        degrees = dict(G.degree())
        max_degree = max(degrees.values()) if degrees else 1
        node_sizes = [node_size * (1 + degrees[node] / max_degree) for node in G.nodes()]
    else:
        node_sizes = [node_size] * len(G.nodes())
    
    # Prepare node and edge traces
    node_trace = go.Scatter(
        x=x_nodes,
        y=y_nodes,
        mode='markers+text',
        text=[str(node) for node in G.nodes()],
        textposition="top center",
        textfont=dict(size=10, color='black'),
        hoverinfo='text',
        marker=dict(
            size=node_sizes,
            color=node_colors_list,
            colorscale=colorscale,
            opacity=node_opacity,
            line=dict(width=1, color='black')
        )
    )
    
    # Create edge traces
    edge_traces = []
    
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        
        edge_trace = go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(width=edge_width, color='grey'),
            hoverinfo='none'
        )
        
        edge_traces.append(edge_trace)
    
    # Create figure
    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            title=f'Graph Visualization (Nodes: {len(G)}, Edges: {len(G.edges())})',
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            width=width,
            height=height
        )
    )
    
    # Save as HTML file for interactive viewing
    fig.write_html(output_file)
    print(f"Interactive graph visualization saved to {output_file}")
    
    # Save as a static image file as well
    image_file = os.path.splitext(output_file)[0] + '.png'
    fig.write_image(image_file)
    print(f"Static graph image saved to {image_file}")
    
    # Print some statistics
    print("\nGraph Statistics:")
    print(f"Number of nodes: {len(G)}")
    print(f"Number of edges: {len(G.edges())}")
    print(f"Average degree: {sum(dict(G.degree()).values()) / len(G):.2f}")
    
    try:
        print(f"Number of connected components: {nx.number_connected_components(G)}")
        largest_cc = max(nx.connected_components(G), key=len)
        print(f"Largest connected component size: {len(largest_cc)}")
    except:
        print("Could not compute connected components (possibly directed graph)")


def main():
    parser = argparse.ArgumentParser(description="Visualize a DOT graph file using Plotly.")
    parser.add_argument('--dot', type=str, default='graph.dot', help='Path to the DOT file.')
    parser.add_argument('--output', type=str, default='graph_vis.html', help='Path to the output HTML file.')
    parser.add_argument('--layout', type=str, default='fruchterman_reingold', 
                       choices=['fruchterman_reingold', 'kamada_kawai', 'circular', 'shell', 'spring', 'spectral', 'random'],
                       help='Layout algorithm to use for node positioning.')
    parser.add_argument('--node-size', type=float, default=15.0, help='Base size of nodes in the visualization.')
    parser.add_argument('--edge-width', type=float, default=1.0, help='Width of edges in the visualization.')
    parser.add_argument('--node-opacity', type=float, default=0.8, help='Opacity of nodes (0-1).')
    parser.add_argument('--max-nodes', type=int, default=1000, 
                       help='Maximum number of nodes to visualize. If the graph has more nodes, a subset will be selected.')
    parser.add_argument('--selection-method', type=str, default='degree', 
                       choices=['degree', 'random', 'connected'],
                       help='Method to select nodes if the graph is too large.')
    parser.add_argument('--colorscale', type=str, default='Viridis', 
                       choices=['Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis', 'Rainbow', 'Blues', 'Reds', 'Greens'],
                       help='Colorscale for node colors.')
    parser.add_argument('--width', type=int, default=1000, help='Width of the plot in pixels.')
    parser.add_argument('--height', type=int, default=800, help='Height of the plot in pixels.')
    parser.add_argument('--no-scale-size', action='store_false', dest='scale_node_size_by_degree',
                       help='Disable scaling node sizes by their degrees.')
    
    args = parser.parse_args()
    
    try:
        # Load the graph
        G = load_dot_file(args.dot)
        
        # Visualize with Plotly
        visualize_with_plotly(
            G, 
            args.output,
            layout=args.layout,
            node_size=args.node_size,
            node_opacity=args.node_opacity,
            edge_width=args.edge_width,
            max_nodes=args.max_nodes,
            selection_method=args.selection_method,
            colorscale=args.colorscale,
            width=args.width,
            height=args.height,
            scale_node_size_by_degree=args.scale_node_size_by_degree
        )
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main() 