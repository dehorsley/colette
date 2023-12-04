import win32com.client

from .base import Message


def send_email(msgs: list[Message], preview=False):
    outlook = win32com.client.Dispatch("Outlook.Application")

    outlook_msgs = []

    for msg in msgs:
        omsg = outlook.CreateItem(0)
        omsg.Subject = msg.subject
        omsg.BodyFormat = 2
        omsg.HTMLBody = msg.body
        omsg.To = ";".join([f"{r.name} <{r.email}>" for r in msg.to])
        outlook_msgs.append(omsg)

        if preview:
            omsg.Display(True)
        else:
            omsg.Send()
