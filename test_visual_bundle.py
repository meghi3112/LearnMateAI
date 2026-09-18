from backend.services.visual_diagram_service import assemble_visual_learning_bundle

test_topics = [
    ('Binary Search Trees', 'Binary Search Tree traversal and lookup algorithm'),
    ('8086 Instruction Set', 'Intel 8086 microprocessor BIU execution unit instruction set architecture'),
    ('OOADP Design Patterns', 'Object Oriented Analysis and Design Patterns, Observer Strategy Factory'),
    ('BA-02 Random Forest Regression', 'Random Forest ensemble regression bagging prediction process'),
    ('Database Normalization', 'Database normalization 1NF vs 2NF vs 3NF Boyce-Codd normal form')
]

for topic, ctx in test_topics:
    bundle = assemble_visual_learning_bundle(topic, ctx)
    print(f"Topic: {topic}")
    print(f"  -> Auto Selected Type: {bundle['auto_selected_type']}")
    print(f"  -> Active Title: {bundle['title']}")
    print(f"  -> Available Types: {list(bundle['all_diagram_types'].keys())}")
    print(f"  -> Reference Diagrams Count: {len(bundle['reference_diagrams'])}")
    for ref in bundle['reference_diagrams'][:2]:
        print(f"     * {ref['title']} | {ref['license']} | {ref['source_url']}")
    print()
