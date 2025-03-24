import argparse
import json
import networkx as nx
import matplotlib.pyplot as plt


def parse_dot(dot_file):
    """Load a DOT file into a networkx graph."""
    try:
        G = nx.drawing.nx_pydot.read_dot(dot_file)
        return G
    except ImportError:
        print("Error: Unable to load the DOT file. Please make sure networkx and pydot are installed.")
        exit(1)


def visualize_graph(G, output_file, layout="spring"):
    """Visualize the graph using matplotlib."""
    plt.figure(figsize=(12, 8))
    
    # Choose layout
    if layout == "spring":
        pos = nx.spring_layout(G, seed=42)
    elif layout == "circular":
        pos = nx.circular_layout(G)
    elif layout == "random":
        pos = nx.random_layout(G)
    elif layout == "shell":
        pos = nx.shell_layout(G)
    else:
        pos = nx.kamada_kawai_layout(G)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color="lightblue")
    nx.draw_networkx_edges(G, pos, width=1, alpha=0.7)
    nx.draw_networkx_labels(G, pos, font_size=8)
    
    plt.title("Network Graph Visualization")
    plt.axis('off')
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Graph image saved to {output_file}")
    
    # Show figure if display is available
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Visualize a DOT file graph using matplotlib.")
    parser.add_argument('--dot', type=str, default='graph.dot', help='Path to the DOT file.')
    parser.add_argument('--output', type=str, default='graph.png', help='Path to the output image file.')
    parser.add_argument('--layout', type=str, default='spring', 
                        choices=['spring', 'circular', 'random', 'shell', 'kamada-kawai'],
                        help='Layout algorithm to use for node positioning.')
    args = parser.parse_args()
    
    G = parse_dot(args.dot)
    visualize_graph(G, args.output, args.layout)


if __name__ == '__main__':
    main() 