import argparse
import pydot


def visualize_dot(dot_file, output_file):
    """Load a DOT file, convert it to a PNG image and save it."""
    graphs = pydot.graph_from_dot_file(dot_file)
    if not graphs:
        print(f"No graph found in {dot_file}")
        exit(1)
    graph = graphs[0]
    graph.write_png(output_file)
    print(f"Graph image saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Visualize a DOT file by converting it into an image.")
    parser.add_argument('--dot', type=str, default='graph.dot', help='Path to the DOT file.')
    parser.add_argument('--output', type=str, default='graph.png', help='Path to the output image file.')
    args = parser.parse_args()
    visualize_dot(args.dot, args.output)


if __name__ == '__main__':
    main() 