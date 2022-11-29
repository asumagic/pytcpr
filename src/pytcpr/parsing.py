import re

timestamp_matcher = re.compile(rb"^\[(\d{2}:\d{2}:\d{2})\] ")

event_matcher = re.compile(r"^@pytcpr!(\w+)~(.*)$")
