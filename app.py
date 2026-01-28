import streamlit as st
import pandas as pd
from pymongo import MongoClient
import smtplib
from email.message import EmailMessage

MONGO_URI = st.secrets['API_KEY']

st.set_page_config(page_title="Recruitment Inventory", layout="wide")


client = MongoClient(MONGO_URI)
db = client["InventoryDB"]
inventory_col = db["Inventory"]
users_col = db["users"]


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = "user"


def login(username, password):
    return users_col.find_one({
        "username": username,
        "password": password
    })


def load_data():
    data = list(inventory_col.find({}, {"_id": 0}))
    if not data:
        return pd.DataFrame(columns=["Item", "Quantity", "Location"])
    return pd.DataFrame(data)

def add_item(item, qty, location):
    inventory_col.insert_one({
        "Item": item,
        "Quantity": qty,
        "Location": location
    })

def update_item(item, qty, location):
    inventory_col.update_one(
        {"Item": item},
        {"$set": {"Quantity": qty, "Location": location}}
    )

def delete_item(item):
    inventory_col.delete_one({"Item": item})


if not st.session_state.logged_in:
    st.title("Inventory Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = login(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = username
               
                st.session_state.role = user.get("role", "user")
                
            else:
                st.error("Invalid username or password")

    st.stop()


st.title("UG Recruitment Inventory")
st.caption(
    f"Logged in as {st.session_state.username} "
    f"({st.session_state.role})"
)

if st.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = "user"
    

df = load_data()


st.subheader("Current Inventory")
st.dataframe(df, use_container_width=True)


st.subheader("Search Item")
search_item = st.text_input("Enter item name to search")

if search_item:
    result = df[df["Item"].str.lower() == search_item.lower()]
    if result.empty:
        st.warning("Item not found.")
    else:
        st.success("Item found:")
        st.dataframe(result)


if st.session_state.role == "admin":

   
    st.subheader("Add Item")

    with st.form("add_item_form"):
        new_item = st.text_input("Item Name")
        new_qty = st.number_input("Quantity", min_value=0, step=1)
        new_location = st.text_input("Location")
        submitted = st.form_submit_button("Add Item")

        if submitted:
            new_item = new_item.strip()
            new_location = new_location.strip()

            if not new_item:
                st.error("Item name cannot be empty.")
            elif new_item.lower() in df["Item"].str.lower().values:
                st.error("Item already exists.")
            else:
                add_item(new_item, new_qty, new_location)
                st.success(f"Added '{new_item}'")
                

    
    st.subheader("Update Item")

    if not df.empty:
        selected_item = st.selectbox("Select item", df["Item"].tolist())
        upd_qty = st.number_input("New Quantity", min_value=0, step=1)
        upd_location = st.text_input("New Location")

        if st.button("Update Item"):
            update_item(selected_item, upd_qty, upd_location.strip())
            st.success(f"Updated '{selected_item}'")
            

    
    st.subheader("Delete Item")

    if not df.empty:
        delete_selected = st.selectbox(
            "Select item to delete",
            df["Item"].tolist(),
            key="delete"
        )

        if st.button("Delete Item"):
            delete_item(delete_selected)
            st.warning(f"Deleted '{delete_selected}'")
            

else:
    st.info("You have view-only access. Inventory changes are restricted to admins.")


def send_request_email(subject: str, body: str):
 
    EMAIL_ADDRESS = st.secrets['EMAIL_ADDRESS']
    EMAIL_PASSWORD = st.secrets['EMAIL_PASSWORD']
    RECIPIENT_EMAIL = st.secrets['RECIPIENT_EMAIL']

    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

st.subheader("Inventory Request")

request_type = st.radio(
    "Request Type",
    ["Request New Item", "Request Refill"]
)

item_name = st.text_input("Item Name")
quantity = st.number_input("Quantity Requested", min_value=1, step=1)
additional_notes = st.text_area("Additional Notes (optional)")

if st.button("Send Request"):
    if not item_name.strip():
        st.error("Item name is required.")
    else:
        subject = f"Inventory Request: {request_type}"
        body = f""" Hello David, please consider the following request to refill/request new item(s)
Requested by: {st.session_state.username}

Request Type:
{request_type}

Item Name:
{item_name}

Quantity:
{quantity}

Additional Notes:
{additional_notes if additional_notes else "N/A"}

Sincerely,
The Inventory Bot
"""
        try:
            send_request_email(subject, body)
            st.success("Request email sent successfully.")
        except Exception as e:
            st.error(f"Error sending email: {e}")


st.markdown("---")

st.markdown("If you have any questions or want to report a bug, email the lead developer Pranat at: pranat32@gmail.com")


