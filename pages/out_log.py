import streamlit as st
import pandas as pd
from pymongo import MongoClient
from email.message import EmailMessage
import smtplib
from io import BytesIO

MONGO_URI = st.secrets["API_KEY"]

st.set_page_config(
    page_title="School Inventory",
    layout="wide"
)

client = MongoClient(MONGO_URI)

db = client["InventoryDB"]
school_inventory_col = db["SchoolInventory"]

# ---------------- SESSION STATE ---------------- #

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = "user"

if not st.session_state.logged_in:
    st.warning("Please log in from the main inventory page.")
    st.stop()

# ---------------- HELPERS ---------------- #

def normalize(text):

    if text is None:
        return ""

    return " ".join(str(text).strip().split())

def load_school_data():

    data = list(
        school_inventory_col.find({}, {"_id": 0})
    )

    columns = [
        "School Name",
        "Contact Name",
        "Contact Info",
        "Item Name",
        "Quantity of Items Sent",
        "Date Sent"
    ]

    if not data:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(data)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    return df[columns]

def get_school_options(df):

    if df.empty:
        return []

    return sorted(
        df["School Name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

# ---------------- DATABASE OPS ---------------- #

def add_school_item(
    item_name,
    qty,
    school_name,
    contact_name,
    contact_info,
    date_sent
):

    school_inventory_col.insert_one({
        "School Name": normalize(school_name),
        "Contact Name": normalize(contact_name),
        "Contact Info": normalize(contact_info),
        "Item Name": normalize(item_name),
        "Quantity of Items Sent": int(qty),
        "Date Sent": str(date_sent)
    })

def delete_school_records(school_name):

    result = school_inventory_col.delete_many({
        "School Name": school_name
    })

    return result.deleted_count

def edit_school_info(
    school_name,
    new_item_name,
    new_qty,
    new_contact_name,
    new_contact_info,
    new_date_sent
):

    update_fields = {}

    if new_item_name:
        update_fields["Item Name"] = normalize(new_item_name)

    if new_qty is not None:
        update_fields["Quantity of Items Sent"] = int(new_qty)

    if new_contact_name:
        update_fields["Contact Name"] = normalize(new_contact_name)

    if new_contact_info:
        update_fields["Contact Info"] = normalize(new_contact_info)

    if new_date_sent is not None:
        update_fields["Date Sent"] = str(new_date_sent)

    if not update_fields:
        return None

    result = school_inventory_col.update_many(
        {"School Name": school_name},
        {"$set": update_fields}
    )

    return result

# ---------------- EMAIL HELPERS ---------------- #

def is_valid_email(address):
    """Basic check: must contain @ and a dot after it."""
    address = normalize(address)
    return "@" in address and "." in address.split("@")[-1]


def send_confirmation_email(
    recipient_email,
    contact_name,
    school_name,
    item_name,
    qty,
    date_sent
):
    """
    Send an auto-generated shipment confirmation email to the contact
    person whenever a new inventory item is added for their school.
    """
    recipient_email = normalize(recipient_email)

    if not is_valid_email(recipient_email):
        return False, (
            f"Confirmation email not sent: '{recipient_email}' "
            "does not look like a valid email address."
        )

    greeting_name = normalize(contact_name) if normalize(contact_name) else "there"

    subject = f"Shipment Confirmation – {normalize(school_name)}"

    body = (
        f"Dear {greeting_name},\n\n"
        f"This is a confirmation that the following item has been shipped to "
        f"{normalize(school_name)}:\n\n"
        f"  Item:      {normalize(item_name)}\n"
        f"  Quantity:  {int(qty)}\n"
        f"  Date Sent: {date_sent}\n\n"
        f"If you have any questions or concerns, please don't hesitate to reach out.\n\n"
        f"Best regards,\n"
        f"School Inventory Team"
    )

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = st.secrets["EMAIL_ADDRESS"]
        msg["To"] = recipient_email
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(
                st.secrets["EMAIL_ADDRESS"],
                st.secrets["EMAIL_PASSWORD"]
            )
            server.send_message(msg)

        return True, f"Confirmation email sent to {recipient_email}."

    except Exception as e:
        return False, f"Item saved, but confirmation email failed: {e}"

# ---------------- LOAD DATA ---------------- #

school_df = load_school_data()

# ---------------- UI ---------------- #

st.title("School Inventory")

st.caption(
    f"Logged in as {st.session_state.username} ({st.session_state.role})"
)

# ---------------- TABLE ---------------- #

st.subheader("Current School Inventory")

st.dataframe(
    school_df,
    use_container_width=True
)

# ---------------- SEARCH ---------------- #

st.subheader("Search School Inventory")

search_school_item = st.text_input(
    "Search by Item Name"
)

if search_school_item:

    search_school_item = normalize(
        search_school_item
    ).lower()

    result = school_df[
        school_df["Item Name"]
        .astype(str)
        .str.lower()
        .str.strip()
        == search_school_item
    ]

    if result.empty:
        st.warning("Item not found.")
    else:
        st.success("Item found.")
        st.dataframe(
            result,
            use_container_width=True
        )

# ---------------- ADMIN ---------------- #

if st.session_state.role == "admin":

    school_options = get_school_options(
        school_df
    )

    # ---------- ADD ---------- #

    st.markdown("---")
    st.subheader("Add School Inventory Item")

    with st.form("add_school_item_form"):

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

        contact_name = st.text_input(
            "Contact Name"
        )

        contact_info = st.text_input(
            "Contact Info (Email address for shipment confirmation)"
        )

        date_sent = st.date_input(
            "Date Sent"
        )

        submitted = st.form_submit_button(
            "Add Item"
        )

        if submitted:

            if not normalize(school_item):

                st.error(
                    "Item name cannot be empty."
                )

            elif not normalize(school_name):

                st.error(
                    "School name cannot be empty."
                )

            else:

                add_school_item(
                    school_item,
                    school_qty,
                    school_name,
                    contact_name,
                    contact_info,
                    date_sent
                )

                st.success("Item added successfully.")

                # --- Auto-send confirmation email to contact ---
                email_sent, email_msg = send_confirmation_email(
                    recipient_email=contact_info,
                    contact_name=contact_name,
                    school_name=school_name,
                    item_name=school_item,
                    qty=school_qty,
                    date_sent=date_sent
                )

                if email_sent:
                    st.info(email_msg)
                else:
                    st.warning(email_msg)

                st.rerun()

    # ---------- DELETE ---------- #

    st.markdown("---")
    st.subheader("Delete School Records")

    if school_options:

        with st.form("delete_school_form"):

            selected_school_delete = st.selectbox(
                "Select School",
                school_options
            )

            delete_submitted = st.form_submit_button(
                "Delete Records"
            )

            if delete_submitted:

                deleted_count = delete_school_records(
                    selected_school_delete
                )

                if deleted_count > 0:

                    st.success(
                        f"Deleted {deleted_count} record(s)."
                    )

                    st.rerun()

                else:

                    st.warning(
                        "No records found."
                    )

    else:

        st.info("No schools available.")

    # ---------- EDIT ---------- #

    st.markdown("---")
    st.subheader("Edit School Info")

    if school_options:

        with st.form("edit_school_form"):

            selected_school_edit = st.selectbox(
                "Select School to Edit",
                school_options
            )

            new_item_name = st.text_input(
                "New Item Name"
            )

            new_qty_text = st.text_input(
                "New Quantity"
            )

            new_contact_name = st.text_input(
                "New Contact Name"
            )

            new_contact_info = st.text_input(
                "New Contact Info"
            )

            update_date = st.checkbox(
                "Update Date"
            )

            new_date_sent = None

            if update_date:

                new_date_sent = st.date_input(
                    "New Date Sent"
                )

            edit_submitted = st.form_submit_button(
                "Update"
            )

            if edit_submitted:

                new_qty = None

                if normalize(new_qty_text):

                    if new_qty_text.isdigit():

                        new_qty = int(
                            new_qty_text
                        )

                    else:

                        st.error(
                            "Quantity must be a whole number."
                        )

                        st.stop()

                result = edit_school_info(
                    selected_school_edit,
                    new_item_name,
                    new_qty,
                    new_contact_name,
                    new_contact_info,
                    new_date_sent
                )

                if result is None:

                    st.error(
                        "No fields provided to update."
                    )

                elif result.modified_count == 0:

                    st.info(
                        "Nothing changed."
                    )

                else:

                    st.success(
                        f"Updated {result.modified_count} record(s)."
                    )

                    st.rerun()

    else:

        st.info("No schools available.")

    # ---------- EMAIL ---------- #

    st.markdown("---")
    st.subheader("Email Inventory")

    with st.form("email_form"):

        recipient_email = st.text_input(
            "Recipient Email"
        )

        email_subject = st.text_input(
            "Email Subject"
        )

        email_body = st.text_area(
            "Email Body"
        )

        email_submitted = st.form_submit_button(
            "Send Email"
        )

        if email_submitted:

            recipient_email = normalize(
                recipient_email
            )

            email_subject = normalize(
                email_subject
            )

            email_body = email_body.strip()

            if not recipient_email:

                st.error(
                    "Recipient email required."
                )

            elif not email_subject:

                st.error(
                    "Subject required."
                )

            elif not email_body:

                st.error(
                    "Body required."
                )

            else:

                try:

                    fresh_df = load_school_data()

                    msg = EmailMessage()

                    msg["Subject"] = email_subject
                    msg["From"] = st.secrets["EMAIL_ADDRESS"]
                    msg["To"] = recipient_email

                    msg.set_content(email_body)

                    excel_buffer = BytesIO()

                    with pd.ExcelWriter(
                        excel_buffer,
                        engine="openpyxl"
                    ) as writer:

                        fresh_df.to_excel(
                            writer,
                            index=False,
                            sheet_name="Inventory"
                        )

                    excel_buffer.seek(0)

                    msg.add_attachment(
                        excel_buffer.read(),
                        maintype="application",
                        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        filename="school_inventory.xlsx"
                    )

                    with smtplib.SMTP_SSL(
                        "smtp.gmail.com",
                        465
                    ) as server:

                        server.login(
                            st.secrets["EMAIL_ADDRESS"],
                            st.secrets["EMAIL_PASSWORD"]
                        )

                        server.send_message(msg)

                    st.success(
                        "Email sent successfully."
                    )

                except Exception as e:

                    st.error(
                        f"Error sending email: {e}"
                    )
