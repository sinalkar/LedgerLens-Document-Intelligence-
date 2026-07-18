import os

import httpx
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")

st.set_page_config(page_title="LedgerLens", page_icon="🧾", layout="wide")

CONFIDENCE_THRESHOLD = float(os.environ.get("REVIEW_CONFIDENCE_THRESHOLD", "0.75"))


def confidence_badge(conf: float) -> str:
    color = "🟢" if conf >= CONFIDENCE_THRESHOLD else "🟠"
    return f"{color} {conf:.2f}"


def upload_page():
    st.header("Upload a receipt or invoice")
    uploaded = st.file_uploader("JPEG or PNG, max 10 MB", type=["jpg", "jpeg", "png"])
    if uploaded is None:
        return
    if not st.button("Extract", type="primary"):
        return

    with st.spinner("Running moderation gate + vision extraction..."):
        try:
            resp = httpx.post(
                f"{API_BASE_URL}/ingest",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                timeout=120,
            )
        except httpx.HTTPError as e:
            st.error(f"API unreachable: {e}")
            return

    if resp.status_code == 422:
        detail = resp.json().get("detail", {})
        reason = detail.get("blocked_reason") if isinstance(detail, dict) else detail
        st.error(f"⛔ Upload blocked by moderation gate — {reason}")
        return
    if resp.status_code != 200:
        st.error(f"Ingest failed ({resp.status_code}): {resp.text}")
        return

    body = resp.json()
    extracted = body["extracted"]

    if body["status"] == "auto_approved":
        st.success("✅ Auto-approved — every field cleared the confidence threshold")
    else:
        st.warning(
            f"🟡 {len(body['flagged_fields'])} field(s) need review: "
            + ", ".join(body["flagged_fields"])
        )

    col_img, col_data = st.columns(2)
    with col_img:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)
    with col_data:
        rows = []
        for field in ["vendor", "invoice_number", "date", "currency", "subtotal", "tax", "total"]:
            rows.append(
                {
                    "field": field,
                    "value": extracted.get(field),
                    "confidence": confidence_badge(extracted.get(f"{field}_confidence", 0.0)),
                }
            )
        st.subheader("Extracted fields")
        st.table(rows)

        if extracted.get("line_items"):
            st.subheader("Line items")
            st.table(
                [
                    {
                        "description": li["description"],
                        "qty": li.get("quantity"),
                        "unit price": li.get("unit_price"),
                        "amount": li["amount"],
                        "confidence": confidence_badge(li["confidence"]),
                    }
                    for li in extracted["line_items"]
                ]
            )

    st.caption(
        f"provider: **{body['provider']}** · model: **{body['model']}** · "
        f"cost: **${body['cost_usd']:.6f}** · doc: `{body['doc_id']}`"
    )


def review_page():
    st.header("Human review queue")
    try:
        items = httpx.get(f"{API_BASE_URL}/review", timeout=30).json()
    except httpx.HTTPError as e:
        st.error(f"API unreachable: {e}")
        return

    if not items:
        st.success("Queue is empty — nothing needs a human right now 🎉")
        return

    by_doc: dict[str, list[dict]] = {}
    for item in items:
        by_doc.setdefault(item["doc_id"], []).append(item)

    for doc_id, doc_items in by_doc.items():
        with st.expander(f"Document `{doc_id}` — {len(doc_items)} flagged field(s)", expanded=True):
            col_img, col_fields = st.columns([1, 2])
            with col_img:
                st.image(f"{API_BASE_URL}{doc_items[0]['image_url']}", use_container_width=True)
            with col_fields:
                edited = st.data_editor(
                    [
                        {
                            "field": i["field_name"],
                            "extracted": i["extracted_value"],
                            "confidence": round(i["confidence"], 2),
                            "correction": "",
                        }
                        for i in doc_items
                    ],
                    disabled=["field", "extracted", "confidence"],
                    key=f"editor-{doc_id}",
                    hide_index=True,
                )
                if st.button("Approve", key=f"approve-{doc_id}", type="primary"):
                    corrections = {
                        row["field"]: row["correction"]
                        for row in edited
                        if row["correction"].strip()
                    }
                    resp = httpx.post(
                        f"{API_BASE_URL}/approve",
                        json={"doc_id": doc_id, "corrections": corrections},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        st.rerun()
                    else:
                        st.error(f"Approve failed: {resp.text}")


def documents_page():
    st.header("Processed documents")
    try:
        docs = httpx.get(f"{API_BASE_URL}/documents", timeout=30).json()
    except httpx.HTTPError as e:
        st.error(f"API unreachable: {e}")
        return
    if not docs:
        st.info("No documents processed yet.")
        return
    st.table(
        [
            {
                "doc": d["doc_id"][:8],
                "file": d["filename"],
                "status": d["status"],
                "vendor": (d["extracted"] or {}).get("vendor"),
                "total": (d["extracted"] or {}).get("total"),
                "provider": d["provider"],
                "cost ($)": round(d["cost_usd"], 6),
                "created": d["created_at"][:19],
            }
            for d in docs
        ]
    )


st.sidebar.title("🧾 LedgerLens")
page = st.sidebar.radio("Page", ["Upload", "Review", "Documents"])
st.sidebar.caption(f"API: {API_BASE_URL}")

if page == "Upload":
    upload_page()
elif page == "Review":
    review_page()
else:
    documents_page()
