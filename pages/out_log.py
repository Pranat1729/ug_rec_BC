from hashlib import new
import re
import streamlit as st
import pandas as pd
from pymongo import MongoClient

MONGO_URI = st.secrets['API_KEY']

st.set_page_config(
    page_title="School Inventory",
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
    st.warning("Please log in from the main inventory page.")
    st.stop()




existing_collections = db.list_collection_names()

if "SchoolInventory" not in existing_collections:

    school_inventory_col.insert_one({
        "School Name": "",
        "Contact Name": "",
        "Contact Info": "",
        "Item Name": "",
        "Quantity of Items Sent": 0,
        "Date Sent": ""
    })

    school_inventory_col.delete_one({
        "School Name": "",
        "Contact Name": "",
        "Contact Info": "",
        "Item Name": "",
        "Quantity of Items Sent": 0,
        "Date Sent": ""
    })




def normalize(s):
    """Strip and collapse internal whitespace."""
    return " ".join(s.split())


def school_name_filter(school_name):
    """Return a case-insensitive, whitespace-tolerant MongoDB filter."""
    return {
        "School Name": {
            "$regex": f"^\\s*{re.escape(normalize(school_name))}\\s*$",
            "$options": "i"
        }
    }


def load_school_data():

    data = list(school_inventory_col.find({}, {"_id": 0}))

    if not data:
        return pd.DataFrame(
            columns=["School Name", "Contact Name", "Contact Info", "Item Name", "Quantity of Items Sent", "Date Sent"]
        )

    return pd.DataFrame(data)





def add_school_item(item_name, qty, school_name, name, email_contact, date_sent):

    school_inventory_col.insert_one({
        "School Name": school_name,
        "Contact Name": name,
        "Contact Info": email_contact,
        "Item Name": item_name,
        "Quantity of Items Sent": qty,
        "Date Sent": str(date_sent)
    })


def delete_school_records_by_name(school_name):

    return school_inventory_col.delete_many(
        school_name_filter(school_name)
    ).deleted_count


def edit_school_info(school_name, new_item_name, new_qty, new_name, new_email_contact, new_date_sent):
    """
    Search by School Name (case-insensitive, whitespace-tolerant).
    Update any combination of: Item Name, Qty, Name, Email/Contact Info.
    Returns the pymongo UpdateResult, or None if no fields to update.
    """

    update_fields = {}

    if new_item_name:
        update_fields["Item Name"] = new_item_name

    if new_qty is not None:
        update_fields["Quantity of Items Sent"] = new_qty

    if new_name:
        update_fields["Contact Name"] = new_name

    if new_email_contact:
        update_fields["Contact Info"] = new_email_contact
        
    if new_date_sent is not None:
        update_fields["Date Sent"] = str(new_date_sent)

    if not update_fields:
        return None

    return school_inventory_col.update_many(
        school_name_filter(school_name),
        {"$set": update_fields}
    )

school_df = load_school_data()


st.title("School Inventory")

st.caption(
    f"Logged in as {st.session_state.username} ({st.session_state.role})"
)




school_df = load_school_data()




st.subheader("Current School Inventory")

st.dataframe(school_df, use_container_width=True)




st.subheader("Search School Inventory")

search_school_item = st.text_input("Search by item name")

if search_school_item:

    result = school_df[
        school_df["Item Name"].str.lower() == search_school_item.lower()
    ]

    if result.empty:
        st.warning("Item not found.")
    else:
        st.success("Item found:")
        st.dataframe(result, use_container_width=True)



if st.session_state.role == "admin":

    st.markdown("---")

    

    st.subheader("Add School Inventory Item")

    with st.form("add_school_item_form"):

        school_item = st.text_input("Item Name")
        school_qty = st.number_input("Qty", min_value=0, step=1)
        school_name = st.text_input("School Name")
        contact_name = st.text_input("Contact Name")
        contact_info = st.text_input("Contact Info")
        date_sent = st.date_input("Date Sent")

        submitted = st.form_submit_button("Add Item")

        if submitted:

            school_item = school_item.strip()
            school_name = school_name.strip()
            contact_name = contact_name.strip()
            contact_info = contact_info.strip()

            if not school_item:
                st.error("Item name cannot be empty.")
            elif not school_name:
                st.error("School name cannot be empty.")
            else:
                add_school_item(
                    school_item,
                    school_qty,
                    school_name,
                    contact_name,
                    contact_info,
                    date_sent
                )
                st.success(f"Added '{school_item}'")
                st.rerun()



    st.markdown("---")
    st.subheader("Delete School Records")

    with st.form("delete_school_by_name_form"):

        school_name_to_delete = st.text_input("School Name to delete")

        delete_submitted = st.form_submit_button("Delete School Records")

        if delete_submitted:

            school_name_to_delete = school_name_to_delete.strip()

            if not school_name_to_delete:
                st.error("School name cannot be empty.")
            else:
                deleted_count = delete_school_records_by_name(school_name_to_delete)

                if deleted_count:
                    st.success(
                        f"Deleted {deleted_count} record(s) for '{school_name_to_delete}'."
                    )
                    st.rerun()
                else:
                    st.warning(
                        f"No records found for '{school_name_to_delete}'."
                    )



    st.markdown("---")
    st.subheader("Edit School Info")

    st.caption(
        "Enter the School Name to find records, then fill in only the fields you want to change."
    )

    with st.form("edit_school_info_form"):

        school_name_to_edit = st.text_input("School Name (used to find records)")

        new_item_name = st.text_input("New Item Name (leave blank to keep current)")
        new_qty_text = st.text_input("New Qty (leave blank to keep current)")
        new_contact_name = st.text_input("New Contact Name (leave blank to keep current)")
        new_contact_info = st.text_input("New Contact Info (leave blank to keep current)")

        update_date_sent = st.checkbox("Update Date Sent")
        if update_date_sent:
            new_date_sent = st.date_input("New Date Sent")
        else:
            new_date_sent = None

        edit_submitted = st.form_submit_button("Update School Info")

        if edit_submitted:

            # Normalize all inputs
            school_name_to_edit = normalize(school_name_to_edit)
            new_item_name = new_item_name.strip()
            new_qty_text = new_qty_text.strip()
            new_contact_name = new_contact_name.strip()
            new_contact_info = new_contact_info.strip()

            if not school_name_to_edit:
                st.error("School name cannot be empty.")
            elif not any([new_item_name, new_qty_text, new_contact_name, new_contact_info, update_date_sent]):
                st.error("Fill in at least one field to update.")
            else:

                # Validate qty
                new_qty = None
                qty_error = False

                if new_qty_text:
                    if new_qty_text.isdigit():
                        new_qty = int(new_qty_text)
                    else:
                        st.error("Qty must be a whole number.")
                        qty_error = True

                if not qty_error:

                    result = edit_school_info(
                        school_name_to_edit,
                        new_item_name,
                        new_qty,
                        new_contact_name,
                        new_contact_info,
                        new_date_sent
                    )

                    if result is None:
                        st.error("No update fields provided.")
                    elif result.matched_count == 0:
                        st.warning(
                            f"No records found for '{school_name_to_edit}'. "
                            "Check the spelling matches exactly what's in the table above."
                        )
                    elif result.modified_count == 0:
                        st.info(
                            f"Records found for '{school_name_to_edit}', "
                            "but the data was already identical — nothing changed."
                        )
                    else:
                        st.success(
                            f"Updated {result.modified_count} record(s) for '{school_name_to_edit}'."
                        )
                        st.rerun()

    st.markdown("---")
    st.subheader("School Inventory Graphs")



    if school_df.empty:
        st.info("No data to display.")


    item_counts = school_df.groupby("Item Name")["Quantity of Items Sent"].sum().reset_index()

    st.bar_chart(item_counts.set_index("Item Name")["Quantity of Items Sent"])
else:

    st.info(
        "You have view-only access. "
        "School inventory changes are restricted to admins."
    )
