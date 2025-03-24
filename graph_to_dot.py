import argparse
import json
import re
import networkx as nx


def parse_nodes(filepath):
    """Parse nodes from a text file. Each node is expected to be on a line starting with '-' and the node name is the text following '-' up to the next ' - '."""
    nodes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('-'):
                parts = line.split(' - ')
                if parts:
                    node = parts[0].lstrip('-').strip()
                    nodes.append(node)
    return nodes


def parse_edges(filepath):
    """Parse edges from a JSON file. This function will fix trailing commas if needed."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r',\s*]', ']', content)
    edges = json.loads(content)
    return edges


def build_graph(nodes_file, edges_file):
    """Build a networkx graph from nodes and edges files."""
    G = nx.Graph()  # using an undirected graph
    
    # Parse and add nodes
    nodes = parse_nodes(nodes_file)
    node_set = set(nodes)  # Create a set for faster lookups
    
    for node in nodes:
        G.add_node(node)
    
    # Parse edges
    edges = parse_edges(edges_file)
    
    # Counters for reporting
    total_edges = len(edges)
    included_edges = 0
    excluded_edges = 0
    
    # Add only edges where both nodes exist in the nodes list
    for edge in edges:
        node1 = edge.get('node1_id')
        node2 = edge.get('node2_id')
        
        # Check if both nodes exist in the node set
        if node1 in node_set and node2 in node_set:
            attr_str = edge.get('attributes', '{}')
            try:
                attributes = json.loads(attr_str)
            except json.JSONDecodeError:
                attributes = {}
            if 'id' in edge:
                attributes['id'] = edge['id']
            
            G.add_edge(node1, node2, **attributes)
            included_edges += 1
        else:
            excluded_edges += 1
    
    print(f"Total edges in JSON: {total_edges}")
    print(f"Edges included in graph: {included_edges}")
    print(f"Edges excluded (missing nodes): {excluded_edges}")
    
    return G


def save_graph_as_dot(G, output_file):
    """Save the networkx graph in DOT format."""
    # Fix node names that contain special characters
    for node in list(G.nodes()):
        if ':' in node:
            # Create a properly quoted version of the node name
            quoted_name = f'"{node}"'
            # Use nx.relabel_nodes to replace the problematic node name
            mapping = {node: quoted_name}
            nx.relabel_nodes(G, mapping, copy=False)
    
    try:
        from networkx.drawing.nx_pydot import write_dot
        write_dot(G, output_file)
    except (ImportError, ValueError, UnicodeEncodeError) as e:
        print(f"Error using NetworkX write_dot: {str(e)}")
        print("Attempting to fix by writing the DOT file directly with UTF-8 encoding...")
        
        # Fallback method: write DOT file directly with UTF-8 encoding
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("graph G {\n")
            for node in G.nodes():
                # Quote node names with special characters or spaces
                safe_node = f'"{node}"' if any(c in node for c in ':#\\" ') else node
                f.write(f'    {safe_node};\n')
            
            for u, v in G.edges():
                # Quote node names with special characters or spaces
                safe_u = f'"{u}"' if any(c in u for c in ':#\\" ') else u
                safe_v = f'"{v}"' if any(c in v for c in ':#\\" ') else v
                f.write(f'    {safe_u} -- {safe_v};\n')
            
            f.write("}\n")


def main():
    parser = argparse.ArgumentParser(description='Parse nodes and edges into a networkx graph and save it as a DOT file.')
    parser.add_argument('--nodes', type=str, default='preview.txt', help='Path to the nodes file.')
    parser.add_argument('--edges', type=str, default='preview_edges.json', help='Path to the edges file.')
    parser.add_argument('--output', type=str, default='graph.dot', help='Path to the output DOT file.')
    args = parser.parse_args()

    G = build_graph(args.nodes, args.edges)
    save_graph_as_dot(G, args.output)
    print(f"Graph saved to {args.output}")


if __name__ == '__main__':
    main()
