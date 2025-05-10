# InsightMapV1

Built with Symbiotic Thinking for the eponymous course.

ChatGPT Tech Stack determination: https://chatgpt.com/share/681fc254-f3c8-8011-8a20-d5a53d64b77d
Claude AI vibe coding: https://claude.ai/share/48ee4a1e-d1c5-425d-b0d5-75ff8192b0dd

## Core Idea
An evolving, spatial map that clusters and links concepts based on semantic similarity and learner context.

## Entity-Predicate Graph Extractor with Coreference Resolution

This application extracts entities and predicates from text using spaCy, TextaCy, and Coreferee for coreference resolution, then visualizes them as an interactive graph using Apache ECharts.

## Features
- Extract entities and predicates from text using NLP
- Resolve coreferences (connecting pronouns like "he", "she", "it" to their referents)
- Visualize relationships as an interactive graph
- Hover over nodes to highlight connections and show predicates
- Right-click to remove nodes and their connections
- Different colors for nouns, pronouns, and referenced entities
- Display pronouns with their referenced entity names (e.g., "he (John)")

## Installation Instructions

### 1. Clone or download the project files
Save all the files in a directory structure like:
```
entity-graph/
├── app.py
├── requirements.txt
└── templates/
    └── index.html
```

### 2. Create a virtual environment
```bash
python3.10 -m venv venv
```

### 3. Activate the virtual environment
- Windows:
```bash
venv\Scripts\activate
```
- macOS/Linux:
```bash
source venv/bin/activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Download spaCy language model and coreferee model
```bash
python -m coreferee install en
python -m spacy download en_core_web_sm
```

### 6. Run the application
```bash
python app.py
```

### 7. Access the application
Open your web browser and go to:
```
http://127.0.0.1:5000/
```

## Docker

Alternatively, youc an use Docker to build and run the application

Build:
```bash
docker build -t insightmap .
```

Run:
```bash
docker run -p 5000:5000 -it insightmap
```

## Usage
1. Enter or paste text into the text area
2. Click "Process Text" to analyze and visualize
3. Hover over nodes to see relationships
4. Right-click nodes to remove them

## How It Works
1. The text is processed using spaCy to parse sentences and identify parts of speech
2. Coreferee is used to resolve coreferences (connecting pronouns to their referents)
3. TextaCy is used to extract key terms and subject-verb-object relationships
4. Pronouns are connected to their referenced entities in the relationship graph
5. The entities and relationships are transformed into a graph format
6. Apache ECharts renders the interactive visualization with special handling for coreferences

## Technical Details
- Backend: Flask + spaCy + TextaCy + Coreferee
- Frontend: HTML, CSS, JavaScript with Apache ECharts
- Graph: Force-directed layout with interactive features
- Coreference resolution: Using Coreferee to connect pronouns to their referenced entities
- Visual enhancements: Different node sizes and colors for canonical entities (those referenced by pronouns)
