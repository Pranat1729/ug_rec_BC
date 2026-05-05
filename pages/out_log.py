import streamlit as st
import pandas as pd
from pymongo import MongoClient

MONGO_URI = st.secrets['API_KEY']

st.set_page_config(
    page_title="out_log",
    layout="wide"
)

client = MongoClient(MONGO_URI)

db = client["InventoryDB"]

school_inventory_col = db["SchoolInventory"]



if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = "user"




if not st.session_state.logged_in:
    st.warning(
        "Please log in from the main inventory page."
    )
    st.stop()




existing_collections = db.list_collection_names()

if "SchoolInventory" not in existing_collections:

    school_inventory_col.insert_one({
        "Item Name": "",
        "Qty": 0,
        "School Name": ""
    })

    school_inventory_col.delete_one({
        "Item Name": "",
        "Qty": 0,
        "School Name": ""
    })


def load_school_data():

    data = list(
        school_inventory_col.find({}, {"_id": 0})
    )

    if not data:

        return pd.DataFrame(
            columns=[
                "Item Name",
                "Qty",
                "School Name"
            ]
        )

    return pd.DataFrame(data)


def add_school_item(
    item_name,
    qty,
    school_name
):

    school_inventory_col.insert_one({

        "Item Name": item_name,
        "Qty": qty,
        "School Name": school_name

    })




st.title("School Inventory")

st.caption(
    f"Logged in as "
    f"{st.session_state.username} "
    f"({st.session_state.role})"
)



school_df = load_school_data()



st.subheader("Current School Inventory")

st.dataframe(
    school_df,
    use_container_width=True
)




st.subheader("Search School Inventory")

search_school_item = st.text_input(
    "Search by item name"
)

if search_school_item:

    result = school_df[
        school_df["Item Name"]
        .str.lower()
        == search_school_item.lower()
    ]

    if result.empty:

        st.warning("Item not found.")

    else:

        st.success("Item found:")

        st.dataframe(
            result,
            use_container_width=True
        )




if st.session_state.role == "admin":

    st.markdown("---")

    st.subheader(
        "Add School Inventory Item"
    )

    with st.form(
        "add_school_item_form"
    ):

        school_item = st.text_input(
            "Item Name"
        )

        school_qty = st.number_input(
            "Qty",
            min_value=0,
            step=1
        )

        school_name = st.text_input(
            "School Name"
        )

        submitted = st.form_submit_button(
            "Add Item"
        )

        if submitted:

            school_item = school_item.strip()
            school_name = school_name.strip()

            if not school_item:

                st.error(
                    "Item name cannot be empty."
                )

            elif not school_name:

                st.error(
                    "School name cannot be empty."
                )

            else:

                add_school_item(
                    school_item,
                    school_qty,
                    school_name
                )

                st.success(
                    f"Added '{school_item}'"
                )

                st.rerun()

else:

    st.info(
        "You have view-only access. "
        "School inventory changes are restricted to admins."
    )
    st.markdown("---")

    st.subheader(
        "Delete School Inventory Item"
    )

    if not school_df.empty:

        delete_selected = st.selectbox(
            "Select item to delete",
            school_df["Item Name"].tolist(),
            key="school_delete"
        )

        if st.button(
            "Delete School Item"
        ):

            delete_school_item(
                delete_selected
            )

            st.warning(
                f"Deleted '{delete_selected}'"
            )

            st.rerun()
