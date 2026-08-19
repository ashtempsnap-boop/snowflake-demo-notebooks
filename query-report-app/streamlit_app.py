import streamlit as st
import os
from datetime import datetime

st.set_page_config(page_title="Query Run Report", page_icon=":bar_chart:", layout="wide")
st.title("Query Run Report")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

session.query_tag = {
    "origin": "sf_sit-is",
    "name": "notebook_demo_pack",
    "version": {"major": 1, "minor": 0},
    "attributes": {"is_quickstart": 1, "source": "streamlit", "vignette": "working_with_git"},
}

# --- Mode selection (replaces the notebook MODE variable) ---
MODE = st.radio("Select mode", ["DEV", "PROD"], horizontal=True)

if MODE == "DEV":
    warehouse_name = "GIT_EXAMPLE_DEV_WH"
    schema_name = "TPCH_SF1"
    size = "XSMALL"
else:
    warehouse_name = "GIT_EXAMPLE_PROD_WH"
    schema_name = "TPCH_SF100"
    size = "LARGE"

st.caption(f"Warehouse: `{warehouse_name}` ({size}) | Schema: `SNOWFLAKE_SAMPLE_DATA.{schema_name}`")

# --- Run pipeline ---
if st.button("Run TPC-H Query"):
    with st.spinner("Setting up warehouse and running query..."):
        session.sql(
            f"CREATE OR REPLACE WAREHOUSE {warehouse_name} WITH WAREHOUSE_SIZE='{size}'"
        ).collect()
        session.sql(f"USE WAREHOUSE {warehouse_name}").collect()
        session.sql(f"USE SCHEMA SNOWFLAKE_SAMPLE_DATA.{schema_name}").collect()

        # Run the TPC-H pricing summary query
        tpch_query = """
            SELECT
                l_returnflag,
                l_linestatus,
                sum(l_quantity) AS sum_qty,
                sum(l_extendedprice) AS sum_base_price,
                sum(l_extendedprice * (1 - l_discount)) AS sum_disc_price,
                sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge,
                avg(l_quantity) AS avg_qty,
                avg(l_extendedprice) AS avg_price,
                avg(l_discount) AS avg_disc,
                count(*) AS count_order
            FROM lineitem
            GROUP BY l_returnflag, l_linestatus
            ORDER BY l_returnflag, l_linestatus
        """
        result_df = session.sql(tpch_query).to_pandas()

        # Get the query ID of the last executed query
        last_query = session.sql(
            "SELECT LAST_QUERY_ID() AS qid"
        ).collect()
        query_id = last_query[0]["QID"]

        # Get query history details
        history_df = session.sql(
            f"SELECT * FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE('{warehouse_name}')) "
            f"WHERE QUERY_ID = '{query_id}'"
        ).to_pandas()

    # Store in session state so the report persists across reruns
    st.session_state["result_df"] = result_df
    st.session_state["query_id"] = query_id
    st.session_state["history_df"] = history_df
    st.session_state["run_time"] = datetime.now()

# --- Display report ---
if "result_df" in st.session_state:
    st.divider()
    st.subheader(f"[{MODE}] Run Report")
    st.caption(f"Generated on: {st.session_state['run_time']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Database", session.get_current_database() or "N/A")
    col2.metric("Schema", session.get_current_schema() or "N/A")
    col3.metric("Warehouse", session.get_current_warehouse() or "N/A")

    st.subheader("Query Results")
    st.dataframe(st.session_state["result_df"], use_container_width=True)

    st.subheader("Query Information")
    st.code(f"Query ID: {st.session_state['query_id']}")

    if not st.session_state["history_df"].empty:
        hist = st.session_state["history_df"]
        if "QUERY_TEXT" in hist.columns:
            with st.expander("Query Text"):
                st.code(hist["QUERY_TEXT"].values[0], language="sql")
        st.subheader("Runtime Information")
        runtime_cols = [c for c in ["START_TIME", "END_TIME", "TOTAL_ELAPSED_TIME"] if c in hist.columns]
        if runtime_cols:
            st.dataframe(hist[runtime_cols], use_container_width=True)
    else:
        st.info("Query history not yet available. It may take a moment to populate.")
else:
    st.info("Click **Run TPC-H Query** to execute the pipeline and generate a report.")
