from bs4 import BeautifulSoup
import re
import os
import phonenumbers
import dateutil.parser
import time
from io import open  # adds emoji support

sms_backup_filename = "./gvoice-all.xml"
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
        # Check if message has an image in it
        images = message.find_all("img")
        if images:
            # Oops should be mms
            write_mms_messages([message.find_all("cite")], [message])
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
    mms_values = {"participants": "~".join(participants)}

    for i in range(len(messages_raw)):
        sender = get_mms_sender(messages_raw[i])
        sent_by_me = sender not in participants

        mms_values["type"] = get_message_type(messages_raw[i])
        mms_values["message"] = get_message_text(messages_raw[i])
        mms_values["time"] = get_time_unix(messages_raw[i])
        mms_values["participants_xml"] = ""
        mms_values["msg_box"] = 2 if sent_by_me else 1
        mms_values["m_type"] = 128 if sent_by_me else 132

        for participant in participants:
            participant_is_sender = participant == sender or (
                sent_by_me and participant == "Me"
            )
            participant_values = {
                "number": participant,
                "code": 137 if participant_is_sender else 151,
            }
            mms_values["participants_xml"] += (
                '    <addr address="%(number)s" charset="106" type="%(code)s"/> \n'
                % participant_values
            )

        mms_text = (
            '<mms address="%(participants)s" ct_t="application/vnd.wap.multipart.related" '
            'date="%(time)s" m_type="%(m_type)s" msg_box="%(msg_box)s" read="1" '
            'rr="129" seen="1" sub_id="-1" text_only="1"> \n'
            "  <parts> \n"
            '    <part ct="text/plain" seq="0" text="%(message)s"/> \n'
            "  </parts> \n"
            "  <addrs> \n"
            "%(participants_xml)s"
            "  </addrs> \n"
            "</mms> \n" % mms_values
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
    # message_text = BeautifulSoup(message.find('q').text,'html.parser').text
    # if 'b2b' in message_text:
    #     images = message.find_all('img')
    #     if images:
    #         print(images[0]['src'])
    return (
        BeautifulSoup(message.find("q").text, "html.parser")
        .prettify(formatter="html")
        .strip()
        .replace('"', "'")
    )


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
