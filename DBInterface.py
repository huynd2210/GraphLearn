import json
import sqlite3

dbName = 'graph.db'
conn = sqlite3.connect(dbName)
cursor = conn.cursor()

def sqlite_to_json(db_name, table_name, output_file):
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Query the data from the specified table
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Get column names from the cursor description
        columns = [description[0] for description in cursor.description]

        # Convert the fetched data to a list of dictionaries
        data = [dict(zip(columns, row)) for row in rows]

        # Convert the list of dictionaries to JSON
        json_data = json.dumps(data, indent=4)

        # Save the JSON data to the output file
        with open(output_file, 'w') as json_file:
            json_file.write(json_data)

        print(f"Data from table '{table_name}' has been successfully exported to {output_file}")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()



def findAllTableNames():
    sql = "SELECT name from sqlite_master where type='table';"

    cursor.execute(sql)

    tables = cursor.fetchall()

    for table in tables:
        print(table[0])
    #graph.db has 2 tables: node and edge

# Example usage
if __name__ == "__main__":
    pass