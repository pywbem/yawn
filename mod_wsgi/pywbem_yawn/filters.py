import markupsafe

def hs(text):
    if getattr(text, 'safe', False):
	return text
    return markupsafe.escape(text)

