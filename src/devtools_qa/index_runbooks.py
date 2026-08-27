from __future__ import annotations

import asyncio
import os

from .infrai_gateway import InfraiGateway


DOCUMENTS = [
    {
        "id": "build-1842",
        "text": "Build 1842 failed during type checking in packages/cli; rerun npm run typecheck after regenerating API types.",
        "event_type": "build",
    },
    {
        "id": "release-2026-08-23",
        "text": "Release 2026.08.23 was promoted after the smoke suite passed; the operation owner was the developer experience team.",
        "event_type": "release",
    },
    {
        "id": "diagnostic-cli-auth",
        "text": "When the CLI reports an expired session, run devtool auth login and repeat the original command.",
        "event_type": "diagnostic",
    },
]


async def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before indexing documents")
    gateway = InfraiGateway(api_key)
    try:
        embedded = [(document, await gateway.embed(document["text"])) for document in DOCUMENTS]
        dimension = len(embedded[0][1])
        await gateway.create_collection("devtools-documents", dimension)
        vectors = [
            {
                "id": document["id"],
                "values": values,
                "metadata": {
                    "document_id": document["id"],
                    "event_type": document["event_type"],
                    "text": document["text"],
                },
            }
            for document, values in embedded
        ]
        await gateway.upsert("devtools-documents", vectors)
        print(f"Indexed {len(vectors)} developer-tools documents")
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
