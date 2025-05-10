from flask import Flask, render_template, request, jsonify
import spacy
import textacy
import textacy.extract
from textacy import extract
import networkx as nx
import json
import coreferee

app = Flask(__name__)

# Load spaCy model with coreferee
nlp = spacy.load("en_core_web_sm")  # Using small model for compatibility
nlp.add_pipe("coreferee")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_text():
    # Get text from request
    text = request.form.get('text', '')
    
    # Process the text
    doc = nlp(text)
    
    # Extract entities and build graph
    graph_data = extract_entities_and_relations(doc)
    
    return jsonify(graph_data)

def extract_entities_and_relations(doc):
    # Initialize components for graph construction
    entities = {}  # Track unique entities
    relationships = []  # Track relationships between entities
    node_id = 0
    
    # =========== ENTITY EXTRACTION ===========
    
    # Track multi-word entities to prevent splitting
    multi_word_entities = set()
    
    # 1. Extract named entities recognized by spaCy
    for ent in doc.ents:
        if len(ent) > 1:  # This is a multi-word entity
            multi_word_entities.add((ent.start, ent.end))
            
        if ent.text.lower() not in entities:
            entities[ent.text.lower()] = {
                "id": f"node{node_id}",
                "name": ent.text,
                "category": ent.label_,
                "mentions": [ent.start],
                "importance": 1,
                "tokens": list(range(ent.start, ent.end))  # Track token ranges
            }
            node_id += 1
    
    # 2. Extract noun chunks for additional entities
    for chunk in doc.noun_chunks:
        # Check if this chunk is part of a larger named entity
        is_part_of_entity = False
        for start, end in multi_word_entities:
            if (chunk.start >= start and chunk.end <= end) or (chunk.start <= start and chunk.end >= end):
                is_part_of_entity = True
                break
                
        if is_part_of_entity:
            continue
            
        # Skip if this is just a determiner or pronoun
        if chunk.root.pos_ in ('DET', 'PRON'):
            continue
            
        # Consider longer noun phrases as entities
        if len(chunk) > 1 or chunk.root.pos_ in ('NOUN', 'PROPN'):
            chunk_text = chunk.text.lower()
            if chunk_text not in entities:
                entities[chunk_text] = {
                    "id": f"node{node_id}",
                    "name": chunk.text,
                    "category": "NOUN_CHUNK",
                    "mentions": [chunk.start],
                    "importance": 1,
                    "tokens": list(range(chunk.start, chunk.end))  # Track token ranges
                }
                node_id += 1
            else:
                # Increment importance for repeated mentions
                entities[chunk_text]["mentions"].append(chunk.start)
                entities[chunk_text]["importance"] += 1
    
    # 3. Process locations and time expressions (important for historical texts)
    for token in doc:
        if token.ent_type_ in ('DATE', 'TIME'):
            # Check if this token is part of a larger entity
            is_part_of_entity = False
            for entity_data in entities.values():
                if token.i in entity_data["tokens"]:
                    is_part_of_entity = True
                    break
                    
            if is_part_of_entity:
                continue
                
            date_text = token.text.lower()
            if date_text not in entities:
                entities[date_text] = {
                    "id": f"node{node_id}",
                    "name": token.text,
                    "category": "TEMPORAL",
                    "mentions": [token.i],
                    "importance": 1,
                    "tokens": [token.i]
                }
                node_id += 1
    
    # =========== COREFERENCE RESOLUTION ===========
    
    # Create a mapping from mentions to their canonical reference
    coref_map = {}  # maps token index to canonical entity text
    canonical_entities = {}  # maps canonical text to its main entity info
    
    # Build coreference mapping
    for chain in doc._.coref_chains:
        # Find the most representative mention (usually the first non-pronoun)
        canonical_mention = None
        for mention in chain.mentions:
            mention_token = doc[mention.root_index]
            if mention_token.pos_ in ('NOUN', 'PROPN'):
                canonical_mention = mention
                break
        
        # If no noun found, use the first mention
        if not canonical_mention and chain.mentions:
            canonical_mention = chain.mentions[0]
        
        if canonical_mention:
            # Get the span for the canonical mention
            # In coreferee, mentions store the root token index, not spans directly
            canonical_token = doc[canonical_mention.root_index]
            canonical_text = canonical_token.text.lower()
            
            # Add canonical entity if it's not already in our entities list
            if canonical_text not in entities:
                entities[canonical_text] = {
                    "id": f"node{node_id}",
                    "name": canonical_token.text,
                    "category": "COREF_ENTITY",
                    "mentions": [canonical_token.i],
                    "importance": 2,  # Higher importance for coreferenced entities
                    "tokens": [canonical_token.i]
                }
                node_id += 1
                canonical_entities[canonical_text] = entities[canonical_text]
            else:
                # Mark this entity as a canonical reference point
                entities[canonical_text]["importance"] += 1
                canonical_entities[canonical_text] = entities[canonical_text]
            
            # Map all mentions to this canonical entity
            for mention in chain.mentions:
                coref_map[mention.root_index] = canonical_text
    
    # =========== RELATION EXTRACTION ===========
    
    # 1. Extract Subject-Verb-Object triples
    for sent in doc.sents:
        triples = textacy.extract.subject_verb_object_triples(sent)
        for triple in triples:
            # In textacy, each part of the triple is a list of tokens
            subj_tokens, verb_tokens, obj_tokens = triple
            
            # Skip if subject or object is missing
            if not subj_tokens or not obj_tokens:
                continue
                
            # Extract the text for each component
            # We'll use the root token of each span as the primary reference
            subj_root = subj_tokens[0] if subj_tokens else None
            verb_root = verb_tokens[0] if verb_tokens else None
            obj_root = obj_tokens[0] if obj_tokens else None
            
            if not subj_root or not verb_root or not obj_root:
                continue
                
            # Get the text for each component
            subj_text = subj_root.text.lower()
            verb_text = verb_root.text
            obj_text = obj_root.text.lower()
            
            # Apply coreference resolution
            if subj_root.i in coref_map:
                subj_text = coref_map[subj_root.i]
            
            if obj_root.i in coref_map:
                obj_text = coref_map[obj_root.i]
            
            # Add entities if they don't exist
            for entity_text, original_token in [(subj_text, subj_root), (obj_text, obj_root)]:
                if entity_text not in entities:
                    entities[entity_text] = {
                        "id": f"node{node_id}",
                        "name": original_token.text,
                        "category": "RELATION_ENTITY",
                        "mentions": [],
                        "importance": 1,
                        "tokens": [original_token.i]
                    }
                    node_id += 1
            
            # Add the relationship
            relationships.append({
                "source": entities[subj_text]["id"],
                "target": entities[obj_text]["id"],
                "value": verb_text
            })
    
    # 2. Extract prepositional relationships
    for token in doc:
        # Check for prepositional phrases
        if token.dep_ == 'pobj' and token.head.dep_ == 'prep':
            # Find what the preposition is attached to
            prep = token.head
            governor = prep.head
            
            # Only process if both the governor and object are nouns
            if governor.pos_ in ('NOUN', 'PROPN', 'VERB') and token.pos_ in ('NOUN', 'PROPN'):
                # Get the text and apply coreference resolution
                gov_text = governor.text.lower()
                obj_text = token.text.lower()
                
                if governor.i in coref_map:
                    gov_text = coref_map[governor.i]
                
                if token.i in coref_map:
                    obj_text = coref_map[token.i]
                
                # Add entities if they don't exist
                for entity_text, original in [(gov_text, governor.text), (obj_text, token.text)]:
                    if entity_text not in entities:
                        entities[entity_text] = {
                            "id": f"node{node_id}",
                            "name": original,
                            "category": "PREP_ENTITY",
                            "mentions": [],
                            "importance": 1,
                            "tokens": [governor.i if entity_text == gov_text else token.i]
                        }
                        node_id += 1
                
                # Add the relationship with the preposition
                relationships.append({
                    "source": entities[gov_text]["id"],
                    "target": entities[obj_text]["id"],
                    "value": prep.text
                })
    
    # 3. Extract temporal relations
    for ent in doc.ents:
        if ent.label_ in ('DATE', 'TIME'):
            # Find verbs associated with this date
            for token in ent.root.children:
                if token.dep_ == 'prep' and token.head.pos_ == 'VERB':
                    # Get the subject of this verb
                    for child in token.head.children:
                        if child.dep_.startswith('nsubj'):
                            # Get the subject text and apply coreference
                            subj_text = child.text.lower()
                            if child.i in coref_map:
                                subj_text = coref_map[child.i]
                            
                            # Ensure entities exist
                            if subj_text not in entities:
                                entities[subj_text] = {
                                    "id": f"node{node_id}",
                                    "name": child.text,
                                    "category": "TEMPORAL_ENTITY",
                                    "mentions": [],
                                    "importance": 1,
                                    "tokens": [child.i]
                                }
                                node_id += 1
                            
                            date_text = ent.text.lower()
                            if date_text not in entities:
                                entities[date_text] = {
                                    "id": f"node{node_id}",
                                    "name": ent.text,
                                    "category": "TEMPORAL",
                                    "mentions": [],
                                    "importance": 1,
                                    "tokens": list(range(ent.start, ent.end))
                                }
                                node_id += 1
                            
                            # Add relationship: "X happened in Y"
                            relationships.append({
                                "source": entities[subj_text]["id"],
                                "target": entities[date_text]["id"],
                                "value": f"{token.head.text} {token.text}"
                            })
    
    # 4. Extract verbs with locational complements
    for token in doc:
        if token.dep_ == 'ROOT' and token.pos_ == 'VERB':
            # Find the subject
            subject = None
            for child in token.children:
                if child.dep_.startswith('nsubj'):
                    subject = child
                    break
            
            if not subject:
                continue
                
            # Find location complements
            for child in token.children:
                if child.dep_ == 'prep' and child.text.lower() in ('in', 'at', 'on', 'to', 'from'):
                    # Find the object of the preposition
                    for pobj in child.children:
                        if pobj.dep_ == 'pobj' and pobj.pos_ in ('NOUN', 'PROPN'):
                            # Apply coreference resolution
                            subj_text = subject.text.lower()
                            if subject.i in coref_map:
                                subj_text = coref_map[subject.i]
                                
                            obj_text = pobj.text.lower()
                            if pobj.i in coref_map:
                                obj_text = coref_map[pobj.i]
                            
                            # Ensure entities exist
                            for entity_text, original in [(subj_text, subject.text), (obj_text, pobj.text)]:
                                if entity_text not in entities:
                                    entities[entity_text] = {
                                        "id": f"node{node_id}",
                                        "name": original,
                                        "category": "LOCATION_ENTITY",
                                        "mentions": [],
                                        "importance": 1,
                                        "tokens": [subject.i if entity_text == subj_text else pobj.i]
                                    }
                                    node_id += 1
                            
                            # Add relationship: "X verb in Y"
                            relationships.append({
                                "source": entities[subj_text]["id"],
                                "target": entities[obj_text]["id"],
                                "value": f"{token.text} {child.text}"
                            })
    
    # =========== GRAPH CONSTRUCTION ===========
    
    # Collect all entities that are part of relationships
    connected_entities = set()
    for rel in relationships:
        source_id = rel['source']
        target_id = rel['target']
        for entity_text, entity_data in entities.items():
            if entity_data["id"] == source_id or entity_data["id"] == target_id:
                connected_entities.add(entity_text)
    
    # Format nodes for the graph, but only include connected ones
    nodes = []
    for entity_text, entity_data in entities.items():
        # Only include nodes that have connections
        if entity_text in connected_entities:
            # Scale node size based on importance score
            node_size = 5 + (entity_data["importance"] * 3)
            
            # Determine if this is a canonical entity (mentioned in coreferences)
            is_canonical = entity_text in canonical_entities
            
            nodes.append({
                "id": entity_data["id"],
                "name": entity_data["name"],
                "category": entity_data["category"],
                "value": node_size,
                "isCanonical": is_canonical
            })
    
    # Deduplicate relationships
    unique_links = set()
    links = []
    
    for rel in relationships:
        # Only keep relationships between connected entities
        source_exists = False
        target_exists = False
        
        for entity_text in connected_entities:
            if entities[entity_text]["id"] == rel["source"]:
                source_exists = True
            if entities[entity_text]["id"] == rel["target"]:
                target_exists = True
        
        if source_exists and target_exists:
            link_key = f"{rel['source']}-{rel['target']}-{rel['value']}"
            if link_key not in unique_links:
                unique_links.add(link_key)
                links.append(rel)
    
    return {
        "nodes": nodes,
        "links": links
    }

if __name__ == '__main__':
    app.run(debug=True)
