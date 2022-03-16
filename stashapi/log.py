# Log messages are transmitted via stderr and are
# encoded with a prefix consisting of special character SOH, then the log
# level (one of t, d, i, w, e - corresponding to trace, debug, info,
# warning and error levels respectively), then special character
# STX.
#
# The trace, debug, info, warning, and error methods, and their equivalent
# formatted methods are intended for use by script scraper instances to transmit log
# messages.

import re, sys, json


def __log(level_char: bytes, s):
	if not level_char:
		return
	level_char = f"\x01{level_char.decode()}\x02"

	# convert dicts to json string
	if isinstance(s, dict):
		s = json.dumps(s)
	# attempt to cast any non string value to a string
	if not isinstance(s, str):
		s = str(s)

	# truncate any base64 data before logging
	s = re.sub(r"data:image.+?;base64(.+?')","[...]",str(s))

	for line in s.split("\n"):
		print(level_char, line, file=sys.stderr, flush=True)

def trace(s):
	__log(b't', s)

def debug(s):
	__log(b'd', s)

def info(s):
	__log(b'i', s)

def warning(s):
	__log(b'w', s)

def error(s):
	__log(b'e', s)

def progress(p):
	progress = min(max(0, p), 1)
	__log(b'p', str(progress))
