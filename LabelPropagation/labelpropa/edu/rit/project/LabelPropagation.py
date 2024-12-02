from neo4j import GraphDatabase
import os
import time
import sys
import json
import traceback

'''
Implementation of the paper - "Near linear time algorithm to detect community structures in large-scale networks"
https://arxiv.org/pdf/0709.2938
'''


def init(driver):
    query = """
        MATCH (n:Node) SET n.label = toString(n.id)
    """

    with driver.session(database="neo4j") as session:
        session.run(query)

def get_communities(driver):
    query = """
        MATCH (n)
        WITH DISTINCT n.label AS label
        RETURN COUNT(label) AS communities
    """
    with driver.session() as session:
        result = session.run(query)
        result = result.single()["communities"]

    return result



def label_propagation(driver, repetitions=1, tolerance = 10, writer=None):

    prev = 0

    for t in range(repetitions):
        # writer.write(f"[INFO]   Repeat = {t+1}\n")

        curr = get_communities(driver)

        # writer.write(f"[INFO]   Communities found = {curr}\n")

        while abs(curr - prev) > tolerance:
            query = """
                MATCH (n)
                WITH n
                ORDER BY rand()
                MATCH (n)-[]->(neighbor)
                WITH n, neighbor.label AS neighborLabel
                WITH n, neighborLabel, COUNT(neighborLabel) AS frequency
                WITH n, COLLECT({label: neighborLabel, count: frequency}) AS labelCounts
                WITH n, labelCounts, MAX(item.count) AS maxCount
                WITH n, [item IN labelCounts WHERE item.count = maxCount] AS majorityLabels
                WITH n, majorityLabels[toInteger(rand() * SIZE(majorityLabels))].label AS selectedLabel
                SET n.label = selectedLabel
                RETURN n.label AS updatedLabel, n
            """
            with driver.session() as session:
                session.run(query)

            prev = curr
        
    # writer.write(f"[INFO]   Done. Influence of seed node id:{seed_id} => {f_seed}\n\n\n")

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

                init(driver)

                label_propagation(driver)


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