import os
import base64
import glob
import json
from jsonschema import validate

def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

def view_docs(client, file, seed_, page_by_page = False):
  schema_path = os.path.join(os.path.dirname(__file__), 'docs_schema.json')
  with open(schema_path, 'r') as schema_file:
      schema = json.load(schema_file)
  
  role={
    "role": "system", 
    "content": "You are a dilligent research assistant. Your role is to carefully look at the attached documents, check whether they contain any redactions, and then transcribe the document, using █ character to denote each and every redacted character, be it a black bar, black or white redaction box, or whited-out text. Next, estimate what percentage of the document is redacted, as the estimated number of redacted characters divided by the total number of characters in the document. Note that this number may be zero if there are no reductions. Finally, these are documents from the fossil sector, and you should list under 'issues' any technologies that are *mentioned in the document* which the industry uses to argue for a delay of substantive climate action, including natural gas, carbon capture and storage, or hydrogen. In most cases, none of these will be mentioned, and you should leave this field empty. Remember, the most important part is to transcribe every redaction box, black bar, or whited out text with █ characters and to keep any terms such as 'Redacted,' 'Redaction, 'Confidential,' 'Privileged,' or 'First Amendment' but surround them with █ characters if they mark a redaction. Some documents include multiple pages and attachments, sometimes with two or more colums of text, transcribe all of it!."
  }
  task={
    "role": "user", 
    "content": "Soon, I will send you an image or a series of image files that comprise one document. Transcribe this document. We use █ characters to denote characters redacted or whited out It is crucial that you are attentive to redactions and transcribe each with the █ character. Insert as many █ characters as you estimate there are redacted text characters. Insert the █ characters in the exact location where the redaction is in the original text, and if if a redaction spans multiple rows of text, then the █ characters should also span multiple rows. The █ characters should follow the text immediately to the left of it, or the text immediately above it if there is no other text in that row. Redactions can take many forms. Make sure to catch every black bar and black redaction box and mark the approximate number of redacted characters by a corresponding number of █ characters. Similarly, don't miss any whited out text characters and use █ characters to denote any whited out text characters. Where there is an incomplete sentence, or floating text without a sentence mark, or a lot of white space followed by a lower case word that lacks context, that is probably a whited-out redaction which you should mark with █ characters. You may also encounter white boxes with a black frame that denote a redaction, again you should mark the approximate count of redacted characters with █ characters. When a box says 'Redacted,' 'Redaction, 'Confidential,' 'Privileged,' or 'First Amendment' or similar in it, it is imperative that you preserve this text and surround it by █ characters, depending on whether it is a white or black box. Finally, there may be bullet points or numbered lists where a list item is missing, again denoting whited-out text you need to mark with █ characters. Remember that not all documents contain redactions. Make sure to include the organization's name where there is a logo etc, but exclude unrelated watermarks (typically across the page). Again, the highest priority is to transcribe every single redaction accurately with █ characters and to keep any words such as 'Redacted,' 'Redaction, 'Confidential,' 'Privileged,' or 'First Amendment,' surrounded by █. Be careful with highlighted text that is not redacted. The documents are in black and white, so highlighted text turned into black on grey background, or even black on dark grey. Try your best to read it, don't assume it's redacted, it might be highlighted, particularly names and organizations. If you can still make out text characters, even just barely, it has just been highlighted. Transcribe every page and every column!"
  }
  pre_task_1 = {
    "role": "user", 
    "content": [
      {"type": "text",
      "text": "Next, I will provide you with a stylized example of a plaintext documents to practice. Find the appropriate positions to insert █ characters to mark redactions:\\n\\nDOCUMENT ID 2024-10572\\n\\nGBG                                                           5/10/2021\\n\\nHi               \\n\\nThank you so much for getting in touch and giving us the opportunity to\\n\\n                                                                     \\n\\nWe are happy to carry out this task for you at a cost of         \\n\\nFurther, I recommend the following course of action:                        Redacted                                       \\n                                                                       \\n\\nIf you are interested, please contact               \\n\\nBest\\nJohn Doe\\n\\nVice President"
      }
    ]
  }
  task_1 = {
    "role": "assistant", 
    "content": [
      {"type": "text", 
      "text": "DOCUMENT ID 2024-10572\\n\\nGBG                                                           5/10/2021\\n\\nHi ██████████████\\n\\nThank you so much for getting in touch and giving us the opportunity to\\n\\n█████████████████████████████████████████████████████████████████████\\n\\nWe are happy to carry out this task for you at a cost of ████████\\n\\nFurther, I recommend the following course of action: ███████████████████████Redacted███████████████████████████████████████\\n███████████████████████████████████████████████████████████████████████\\n\\nIf you are interested, please contact ██████████████\\n\\nBest\\nJohn Doe\\n\\nVice President"
      }
    ]
  }
  pre_task_2 = {
    "role": "user", 
    "content": [
      {"type": "text",
      "text": "This is another stylized examplef for you to practice and insert █ characters to mark redactions:DOCUMENT ID 2024-9471\\n\\nHi Mr. John Doe\\n\\nPlease see the attached letter.\\n\\nDOCUMENT ID 2024-9471\\n\\Confidential -- do not circulate.                  GBG-9410\\n\\nDOCUMENT ID 2024-9471\\n\\n-------------------------------------------------------Privileged – First Amendment---------------------------------\\n\\nConfidential -- do not circulate.                  GBG-9410"
      }
    ]
  }
  task_2 = {
    "role": "assistant", 
    "content": [
      {"type": "text", 
      "text": "This is another stylized examplef for you to practice and insert █ characters to mark redactions:DOCUMENT ID 2024-9471\\n\\nHi Mr. John Doe\\n\\nPlease see the attached letter.\\n\\nDOCUMENT ID 2024-9471\\n\\Confidential -- do not circulate.                  GBG-9410\\n\\nDOCUMENT ID 2024-9471\\n\\n███████████████████████████████████████████████████████Privileged – First Amendment█████████████████████████████████\\n\\nConfidential -- do not circulate.                  GBG-9410"
      }
    ]
  }
  announce_docs = {
    "role": "user", 
    "content": [
      {
        "type": "text", 
        "text": "Next is the document, which will consist of one or more image files. Transcribe every page. Remember to retain any text such as 'Redacted,' 'Redaction, 'Confidential,' 'Privileged,' or 'First Amendment,' surround it by █, and to transcribe any redaction, be it a black bar, labelled redaction box, or whited out text, with the █ character. It is imperative that you transcribe every individual redaction with a number of █ characters! Emails can have attachments, or a document may be a collection of reports, so the contents may be disjointed - it is critical that you transcribe everything, every page and every column, except for background watermark objects."}
    ]
  }
  
  os.system(f"cp {file} temp/tmp.pdf")
  os.system(f"pdftoppm -jpeg temp/tmp.pdf temp/tmp")
  pages = sorted(glob.glob("temp/tmp-*"))
  
  for page in pages:
    image = encode_image(page)
    announce_docs['content'].append({"type": "image_url", "image_url": { "url": f"data:image/jpeg;base64,{image}"}})
    
  messages_ = [role, pre_task_1, task_1, announce_docs]
  # messages_ = [role, pre_task_1, task_1, pre_task_2, task_2, announce_docs]
  # This failed

  response = client.beta.chat.completions.parse(
    model = "gpt-4o-2024-08-06",
    messages = messages_,
    seed = seed_,
    response_format = schema
  )
  os.system("rm temp/tmp*")
  return response
