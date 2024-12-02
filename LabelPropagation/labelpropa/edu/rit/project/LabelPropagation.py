from neo4j import GraphDatabase
import os
import time
import sys
import json
import traceback

def main():
    neo4j_url = sys.argv[1]
    neo4j_folder = sys.argv[2]
    input_filename = sys.argv[3]

    with open(input_filename) as fopen:
        contents = fopen.readlines()

    contents = f"[{','.join(contents)}]"
    contents = json.loads(contents)

    try:

        for query in contents:
            db_name = query["database"]
            with get_neo4j_connection(neo4j_folder, db_name, neo4j_url) as driver:
                driver.verify_connectivity()

                with driver.session(database="neo4j") as session:
                    # TODO label propagation code
                    pass


        driver = get_neo4j_connection(neo4j_folder, 'fake-db', neo4j_url)
        driver.close()
    except Exception:
        print(traceback.format_exc())


def get_neo4j_connection(folder, db_name, url):
    # Since Neo4j community edition does not support multiple schemas, we are forced
    #   to come up with all these stuff. Thanks a lot, Neo4j!
    # This is expecting Neo4jEmbeddedMultiple is running.

    # If ./SNA is the Neo4j folder, this will access ./SNA/{db_name}/
    with open(os.path.join(folder, db_name + '.swap'), 'w') as fw:
        fw.write('\n')

    # It takes a little bit. Add more secs if needed!
    time.sleep(60.0)

    return GraphDatabase.driver(url, database='neo4j')


if __name__ == "__main__":
    main()