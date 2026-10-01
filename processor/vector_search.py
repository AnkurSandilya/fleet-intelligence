import os
import pickle

import faiss
import numpy as np
import psycopg2
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

MODEL_NAME = "all-MiniLM-L6-v2"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "fleet_db"),
    "user": os.getenv("DB_USER", "fleet_user"),
    "password": os.getenv("DB_PASSWORD", "fleet_password"),
}

INDEX_DIR = "vector_index"
INDEX_PATH = os.path.join(INDEX_DIR, "incidents.faiss")
MAPPING_PATH = os.path.join(INDEX_DIR, "incident_ids.pkl")


# ---------------------------------------------------------
# Embedding model
# ---------------------------------------------------------

model = SentenceTransformer(MODEL_NAME)


# ---------------------------------------------------------
# Convert incident → embedding
# ---------------------------------------------------------

def embed_incident(incident):
    text = (
        f"{incident['incident_type']} "
        f"vehicle={incident['vehicle_code']} "
        f"severity={incident['severity']} "
        f"description={incident['description'] or ''}"
    )

    embedding = model.encode(
        text,
        convert_to_numpy=True
    )

    return embedding.astype("float32")


# ---------------------------------------------------------
# Build FAISS index
# ---------------------------------------------------------

def build_index():
    connection = psycopg2.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            i.incident_id,
            i.incident_type,
            i.severity,
            i.description,
            v.vehicle_id,
            CONCAT('VH', LPAD(v.vehicle_id::text, 6, '0')) AS vehicle_code
        FROM incident i
        JOIN vehicle v
            ON i.vehicle_id = v.vehicle_id
        ORDER BY i.incident_id
        """
    )

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    if not rows:
        print("No incidents found in PostgreSQL.")
        return

    incidents = []

    for row in rows:
        (
            incident_id,
            incident_type,
            severity,
            description,
            vehicle_id,
            vehicle_code,
        ) = row

        incidents.append({
            "incident_id": incident_id,
            "incident_type": incident_type,
            "severity": severity,
            "description": description,
            "vehicle_id": vehicle_id,
            "vehicle_code": vehicle_code,
        })

    embeddings = []

    for incident in incidents:
        embeddings.append(embed_incident(incident))

    embeddings = np.vstack(embeddings).astype("float32")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(embeddings)

    os.makedirs(INDEX_DIR, exist_ok=True)

    faiss.write_index(index, INDEX_PATH)

    incident_ids = [
        incident["incident_id"]
        for incident in incidents
    ]

    with open(MAPPING_PATH, "wb") as file:
        pickle.dump(incident_ids, file)

    print(f"Indexed {index.ntotal} incidents.")
    print(f"Vector dimension: {dimension}")
    print(f"Saved: {INDEX_PATH}")
    print(f"Saved: {MAPPING_PATH}")


# ---------------------------------------------------------
# Semantic search
# ---------------------------------------------------------

def search(query, k=10):
    """
    Search incidents using semantic similarity.

    Returns ranked incident records from PostgreSQL.
    """

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(
            f"FAISS index not found: {INDEX_PATH}"
        )

    if not os.path.exists(MAPPING_PATH):
        raise FileNotFoundError(
            f"Incident mapping not found: {MAPPING_PATH}"
        )

    # Load FAISS index
    index = faiss.read_index(INDEX_PATH)

    # Load FAISS row → incident_id mapping
    with open(MAPPING_PATH, "rb") as file:
        incident_ids = pickle.load(file)

    # Convert query into embedding
    query_vector = model.encode(
        query,
        convert_to_numpy=True
    ).astype("float32")

    query_vector = np.expand_dims(query_vector, axis=0)

    # Don't request more results than exist
    k = min(k, index.ntotal)

    distances, indices = index.search(query_vector, k)

    # Convert FAISS positions to database incident IDs
    matched_ids = []

    for distance, index_position in zip(
        distances[0],
        indices[0]
    ):
        if index_position < 0:
            continue

        incident_id = incident_ids[index_position]

        matched_ids.append(
            (incident_id, float(distance))
        )

    if not matched_ids:
        return []

    # -----------------------------------------------------
    # Fetch complete incident information
    # -----------------------------------------------------

    connection = psycopg2.connect(**DB_CONFIG)
    cursor = connection.cursor()

    ids = [incident_id for incident_id, _ in matched_ids]

    cursor.execute(
        """
        SELECT
            i.incident_id,
            i.vehicle_id,
            CONCAT('VH', LPAD(i.vehicle_id::text, 6, '0')) AS vehicle_code,
            i.incident_type,
            i.severity,
            i.description,
            i.event_timestamp,
            i.latitude,
            i.longitude
        FROM incident i
        WHERE i.incident_id = ANY(%s)
        """,
        (ids,)
    )

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    # Map database rows by incident_id
    row_map = {
        row[0]: row
        for row in rows
    }

    # Preserve FAISS ranking
    results = []

    for incident_id, distance in matched_ids:

        row = row_map.get(incident_id)

        if row is None:
            continue

        (
            incident_id,
            vehicle_id,
            vehicle_code,
            incident_type,
            severity,
            description,
            event_timestamp,
            latitude,
            longitude,
        ) = row

        results.append({
            "incident_id": incident_id,
            "vehicle_id": vehicle_id,
            "vehicle_code": vehicle_code,
            "incident_type": incident_type,
            "severity": severity,
            "description": description,
            "event_timestamp": event_timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "distance": distance,
        })

    return results


# ---------------------------------------------------------
# Test search
# ---------------------------------------------------------

if __name__ == "__main__":

    query = "vehicles overheating while stopped"

    print()
    print("Semantic search:")
    print(f"Query: {query}")
    print()

    results = search(query, k=10)

    for rank, result in enumerate(results, start=1):

        print(
            f"{rank}. "
            f"{result['vehicle_code']} | "
            f"{result['incident_type']} | "
            f"{result['severity']} | "
            f"distance={result['distance']:.4f}"
        )
