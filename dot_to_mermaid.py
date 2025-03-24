import argparse
import pydot
import re
import networkx as nx


def dot_to_mermaid(dot_file, output_file, direction="TD"):
    """Convert a DOT file to Mermaid format.
    
    Args:
        dot_file: Path to the DOT file
        output_file: Path to save the Mermaid file
        direction: Direction of the graph (TD=top-down, LR=left-right)
    """
    try:
        # First try with pydot
        graphs = pydot.graph_from_dot_file(dot_file)
        if not graphs:
            print(f"No graph found in {dot_file}")
            exit(1)
        
        graph = graphs[0]
        
        # Start building Mermaid syntax
        mermaid = f"graph {direction};\n"
        
        # Add edges
        for edge in graph.get_edges():
            source = edge.get_source().strip('"')
            dest = edge.get_destination().strip('"')
            
            # Handle edge attributes (like labels)
            attrs = edge.get_attributes()
            if 'label' in attrs:
                label = attrs['label'].strip('"')
                mermaid += f"    {source}-->|{label}|{dest};\n"
            else:
                mermaid += f"    {source}-->{dest};\n"
                
        # Write to file with UTF-8 encoding
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(mermaid)
            
        print(f"Mermaid diagram saved to {output_file}")
        
    except Exception as e:
        print(f"Error with pydot approach: {e}")
        print("Falling back to NetworkX...")
        
        try:
            # Try with NetworkX
            G = nx.drawing.nx_pydot.read_dot(dot_file)
            
            # Start building Mermaid syntax
            mermaid = f"graph {direction};\n"
            
            # Add edges
            for u, v, data in G.edges(data=True):
                # Ensure proper unicode handling by explicitly converting to string
                source = str(u).strip('"')
                dest = str(v).strip('"')
                
                # Handle edge labels
                if 'label' in data:
                    label = str(data['label']).strip('"')
                    mermaid += f"    {source}-->|{label}|{dest};\n"
                else:
                    mermaid += f"    {source}-->{dest};\n"
            
            # Write to file with UTF-8 encoding
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(mermaid)
                
            print(f"Mermaid diagram saved to {output_file}")
            
        except Exception as e:
            print(f"Error with NetworkX approach: {e}")
            print("Falling back to direct file parsing...")
            
            try:
                # Direct file parsing approach with proper UTF-8 encoding
                with open(dot_file, 'r', encoding='utf-8') as f:
                    dot_content = f.read()
                
                # Start building Mermaid syntax
                mermaid = f"graph {direction};\n"
                
                # Parse edges using regex
                # This pattern matches both directed and undirected edges in DOT syntax
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
                        mermaid += f"    {source}-->{dest};\n"
                    elif '--' in line:  # Simpler fallback for edges
                        parts = line.split('--')
                        if len(parts) >= 2:
                            source = parts[0].strip().strip('"')
                            dest = parts[1].strip().strip('"').split(';')[0].strip().strip('"')
                            mermaid += f"    {source}-->{dest};\n"
                
                # Write to file with UTF-8 encoding
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(mermaid)
                    
                print(f"Mermaid diagram saved to {output_file} using direct file parsing")
                
            except Exception as e:
                print(f"Error with direct file parsing: {e}")
                exit(1)


def main():
    parser = argparse.ArgumentParser(description="Convert a DOT file to Mermaid format.")
    parser.add_argument('--dot', type=str, default='graph.dot', help='Path to the DOT file.')
    parser.add_argument('--output', type=str, default='graph.mmd', help='Path to the output Mermaid file.')
    parser.add_argument('--direction', type=str, default='TD', choices=['TD', 'LR'], 
                       help='Direction of the graph (TD=top-down, LR=left-right)')
    args = parser.parse_args()
    
    dot_to_mermaid(args.dot, args.output, args.direction)


if __name__ == '__main__':
    main() 