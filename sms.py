from bs4 import BeautifulSoup
import html
import re
import os
import phonenumbers
import dateutil.parser
import time
from io import open  # adds emoji support
from pathlib import Path

sms_backup_filename = "./gvoice-all.xml"
sms_backup_path = Path(sms_backup_filename)
# Clear file if it already exists
sms_backup_path.open("w").close()
print("New file will be saved to " + sms_backup_filename)


def main():
    print("Checking directory for *.html files")
    num_sms = 0
    root_dir = "."

    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            sms_filename = os.path.join(subdir, file)

            try:
                sms_file = open(sms_filename, "r", encoding="utf8")
            except FileNotFoundError:
                continue

            if os.path.splitext(sms_filename)[1] != ".html":
                # print(sms_filename,"- skipped")
                continue

            print("Processing " + sms_filename)

            is_group_conversation = re.match(r"(^Group Conversation)", file)

            soup = BeautifulSoup(sms_file, "html.parser")

            messages_raw = soup.find_all(class_="message")

            num_sms += len(messages_raw)

            if is_group_conversation:
                participants_raw = soup.find_all(class_="participants")
                write_mms_messages(participants_raw, messages_raw)
            else:
                write_sms_messages(file, messages_raw)

    sms_backup_file = open(sms_backup_filename, "a")
    sms_backup_file.write("</smses>")
    sms_backup_file.close()

    write_header(sms_backup_filename, num_sms)


def write_sms_messages(file, messages_raw):
    fallback_number = 0
    title_has_number = re.search(r"(^\+*[0-9]+)", file)
    if title_has_number:
        fallback_number = title_has_number.group()

    sms_values = {"phone": get_first_phone_number(messages_raw, fallback_number)}

    sms_backup_file = open(sms_backup_filename, "a", encoding="utf8")
    for message in messages_raw:
        # Check if message has an image in it and treat as mms if so
        if message.find_all("img"):
            # Sometimes these messages don't fill out the tel field. Use a sensible default.
            participants_raw = message.find_all("cite")
            for participant in participants_raw:
                if not participant.a["href"][4:0]:
                    participant.a["href"] = f'tel:{sms_values["phone"]}'

            write_mms_messages([participants_raw], [message])
            continue

        sms_values["type"] = get_message_type(message)
        sms_values["message"] = get_message_text(message)
        sms_values["time"] = get_time_unix(message)
        sms_text = (
            '<sms protocol="0" address="%(phone)s" '
            'date="%(time)s" type="%(type)s" '
            'subject="null" body="%(message)s" '
            'toa="null" sc_toa="null" service_center="null" '
            'read="1" status="1" locked="0" /> \n' % sms_values
        )
        sms_backup_file.write(sms_text)

    sms_backup_file.close()


def write_mms_messages(participants_raw, messages_raw):
    sms_backup_file = open(sms_backup_filename, "a", encoding="utf8")

    participants = get_participant_phone_numbers(participants_raw)
    participants_text = "~".join(participants)

    for message in messages_raw:
        sender = get_mms_sender(message)
        sent_by_me = sender not in participants

        # Handle images
        images = message.find_all("img")
        image_parts = ""
        if images:
            for image in images:
                image_filename = image["src"]
                # Each image found should only match a single file
                image_path = list(Path.cwd().glob(f"**/{image_filename}*"))
                assert (
                    len(image_path) == 1
                ), "Multiple potential matching images found. Unhandled. Images: f{image_path!r}"
                image_path = image_path[0]
                print(image_path.resolve())
                image_parts += (
                    f'    <part ct="text/plain" seq="0" text="{image_path}"/> \n'
                )

        # type = get_message_type(message)
        message_text = get_message_text(message)
        time = get_time_unix(message)
        participants_xml = ""
        msg_box = 2 if sent_by_me else 1
        m_type = 128 if sent_by_me else 132

        for participant in participants:
            participant_is_sender = participant == sender or (
                sent_by_me and participant == "Me"
            )
            participant_values = {
                "number": participant,
                "code": 137 if participant_is_sender else 151,
            }
            participants_xml += (
                '    <addr address="%(number)s" charset="106" type="%(code)s"/> \n'
                % participant_values
            )

        mms_text = (
            f'<mms address="{participants_text}" ct_t="application/vnd.wap.multipart.related" '
            f'date="{time}" m_type="{m_type}" msg_box="{msg_box}" read="1" '
            'rr="129" seen="1" sub_id="-1" text_only="1"> \n'
            "  <parts> \n"
            f'    <part ct="text/plain" seq="0" text="{message_text}"/> \n'
            + image_parts
            + "  </parts> \n"
            "  <addrs> \n"
            f"{participants_xml}"
            "  </addrs> \n"
            "</mms> \n"
        )

        sms_backup_file.write(mms_text)

    sms_backup_file.close()


def get_message_type(message):  # author_raw = messages_raw[i].cite
    author_raw = message.cite
    if not author_raw.span:
        return 2
    else:
        return 1

    return 0


def get_message_text(message):
    # print(message)

    # Attempt to properly translate newlines. Might want to translate other HTML here, too.
    # This feels very hacky, but couldn't come up with something better.
    message_text = html.escape(
        str(message.find("q")).strip()[3:-4].replace("<br/>", "((br/))"), quote=True
    ).replace("((br/))", "&#10;")

    return message_text


def get_mms_sender(message):
    return format_number(phonenumbers.parse(message.cite.a["href"][4:], None))


def get_first_phone_number(messages, fallback_number):
    # handle group messages
    for author_raw in messages:
        if not author_raw.span:
            continue

        sender_data = author_raw.cite

        try:
            phone_number = phonenumbers.parse(sender_data.a["href"][4:], None)
        except phonenumbers.phonenumberutil.NumberParseException:
            return sender_data.a["href"][4:]

        return format_number(phone_number)

    # fallback case, use number from filename
    if fallback_number == 0 or len(fallback_number) < 7:
        return fallback_number
    else:
        return format_number(phonenumbers.parse(fallback_number, None))


def get_participant_phone_numbers(participants_raw):
    # Having your own number in the participants list does not appear to be a requirement
    default_participants = [
        "Me"
    ]  # May require adding a contact for "Me" to your phone, with your current number
    participants = []

    for participant_set in participants_raw:
        # print(participant_set)
        for participant in participant_set:
            # print(participant)
            if not hasattr(participant, "a"):
                continue

            try:
                phone_number = phonenumbers.parse(participant.a["href"][4:], None)
            except phonenumbers.phonenumberutil.NumberParseException:
                participants.push(participant.a["href"][4:])

            participants.append(format_number(phone_number))

    return participants


def format_number(phone_number):
    return phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.E164)


def get_time_unix(message):
    time_raw = message.find(class_="dt")
    ymdhms = time_raw["title"]
    time_obj = dateutil.parser.isoparse(ymdhms)
    # print(time_obj)
    mstime = time.mktime(time_obj.timetuple()) * 1000
    return int(mstime)


def write_header(filename, numsms):
    backup_file = open(filename, "r", encoding="utf8")
    backup_text = backup_file.read()
    backup_file.close()

    backup_file = open(filename, "w", encoding="utf8")
    backup_file.write("<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n")
    backup_file.write("<!--Converted from GV Takeout data -->\n")
    backup_file.write('<smses count="' + str(numsms) + '">\n')
    backup_file.write(backup_text)
    backup_file.close()


main()
