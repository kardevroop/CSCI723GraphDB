from neo4j import GraphDatabase
import os
import time
import sys
import json
import traceback
import copy

'''
Implementation of the paper - "Near linear time algorithm to detect community structures in large-scale networks"
https://arxiv.org/pdf/0709.2938
'''


def init(driver):

    with driver.session(database="neo4j") as session:
        # session.run("MATCH (n:Node) REMOVE n.seed_label")
        session.run("MATCH (n:Node) SET n.seed_label = n.id")

def get_communities(driver):
    query = """
        MATCH (n)
        WITH DISTINCT n.seed_label AS label
        RETURN COUNT(label) AS communities
    """
    with driver.session() as session:
        result = session.run(query)
        result = result.single()["communities"]

    return result

def calculate_jaccard_similarity(a: set = None, b:set = None):
    a_and_b = a.intersection(b)
    a_or_b = a.union(b)

    return len(a_and_b) * 1.0 / len(a_or_b)

def calculate_sorensen_similarity(a: set = None, b:set = None):
    a_and_b = a.intersection(b)

    return len(a_and_b) * 2.0 / (len(a) + len(b))

def calculate_overlap_similarity(a: set = None, b:set = None):
    a_and_b = a.intersection(b)

    return len(a_and_b) * 1.0 / min(len(a), len(b))

def calculate_similarity(a:set=None, b:set=None, type="Jaccard"):
    if a is None or b is None:
        return 0.0
    
    if type == 'Jaccard':
        return calculate_jaccard_similarity(a, b)
    elif type == 'Sorensen':
        return calculate_sorensen_similarity(a, b)
    # elif type == 'Tversky':
    #     return calculate_tversky_similarity(a, b)

    return calculate_overlap_similarity(a, b)

def combine_overlapping_sets(list_of_sets):

    result = []
    while list_of_sets:
        current_set = list_of_sets.pop()
        sets_to_merge = []

        for i, other_set in enumerate(list_of_sets):
            if current_set.intersection(other_set):
                sets_to_merge.append(i)

        for index in sorted(sets_to_merge, reverse=True):
            current_set.update(list_of_sets.pop(index))

        result.append(current_set)

    return result

def evaluate(driver, gt, similarity='Jaccard', penalty=None, writer=None):

    communities = []

    with driver.session() as session:
        query = """
            MATCH (n)
            WITH n.seed_label as community, COLLECT(n.id) AS ids
            RETURN community, ids
            ORDER BY community
        """
        result = session.run(query)

        for r in result:
            communities.append(set(r["ids"]))
    
    # writer.write(f"[INFO]   {communities}\n")

    unmatched = []
    wt_avg = 0.0

    # n = len(communities)
    # communities_copy = copy.deepcopy(communities)
    similarities = []
    for a in gt:
        max_sim = -sys.maxsize
        match = None

        for b in communities:
            sim = calculate_similarity(a=a, b=b, type=similarity)
            if sim > max_sim and abs(sim - 0.0) > 0.01:
                max_sim = sim
                match = b

        if match is not None and match in communities:
            similarities.append(max_sim)
            communities.remove(match)

        elif match is None:
            unmatched.append(a)

    unmatched = combine_overlapping_sets(unmatched)
    writer.write(f"[INFO]   Unmatched non-overlapping ground truth communities: {len(unmatched)}\n")

    unmatched = len(unmatched)

    wt_avg = sum(similarities)
    n = len(similarities)

    if penalty:

        # Penalty if there are communities in gt which are unmatched
        # wt_avg += unmatched * (-1.0 * unmatched / len(gt))
        n += unmatched

        # Penalty if there are communities in `communities` which are extra
        rem=0
        for _ in communities:
            rem += 1
        writer.write(f"[INFO]   Unmatched generated communities: {rem}\n")
        n += rem



    writer.write(f"[INFO]   {similarity} similarity index with{''if penalty else 'out'} penalty: {max(0.0, 1.0 * wt_avg / n)}\n")

    return max(0.0, 1.0 * wt_avg / n)


def label_propagation(driver, repetitions=1, tolerance = 0, writer=None):

    prev = 0

    for t in range(repetitions):
        writer.write(f"[INFO]   Repeat = {t+1}\n")

        curr = get_communities(driver)
        writer.write(f"[INFO]   Communities found = {curr}\n")

        if abs(curr - prev) <= tolerance:
            break

        with driver.session() as session:

            query = """
                MATCH (n)
                WITH n
                ORDER BY rand()
                MATCH (n)-[]->(neighbor)
                WITH n, neighbor.seed_label AS neighborLabel
                WITH n, neighborLabel, COUNT(neighborLabel) AS frequency
                WITH n, COLLECT({label: neighborLabel, count: frequency}) AS labelCounts
                WITH n, labelCounts, REDUCE(maxRecord = 0, record IN labelCounts |
                    CASE
                        WHEN record.count > maxRecord THEN record.count
                        ELSE maxRecord
                    END
                ) AS maxCount
                WITH n, [item IN labelCounts WHERE item.count = maxCount] AS majorityLabels
                WITH n, majorityLabels[toInteger(rand() * SIZE(majorityLabels))].label AS selectedLabel
                SET n.seed_label = selectedLabel
                RETURN n.seed_label AS updatedLabel, n
            """
            session.run(query)

        prev = curr
        
    writer.write("[INFO]   Done. \n")

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
            db_name, t, epsilon, similarity, gt_file = query["database"], query["repetitions"], query["tolerance"], query.get("similarity"), query.get("gt_file")
            gt = []
            log_path = os.path.join("logs", f"{db_name}")
            if not os.path.exists(log_path):
                os.makedirs(log_path)
            f = open(os.path.join(log_path, "log.txt"), 'a+')
            f.write(f"[INFO]    Test case: {query}\n\n")

            with get_neo4j_connection(neo4j_folder, db_name, neo4j_url) as driver:
                driver.verify_connectivity()

                init(driver)

                label_propagation(driver, repetitions=t, tolerance=epsilon, writer=f)

                if gt_file is not None:
                    with open(gt_file) as gt_open:
                        lines = gt_open.readlines()
                        for l in lines:
                            gt.append(set([int(a) for a in l.split()]))

                    f.write(f"[INFO]    Ground Truth communities: {len(gt)}\n")

                    evaluate(driver, gt, similarity=similarity, penalty=True, writer=f)

            f.write("\n\n")
        
            f.close()

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