import os
import base64
import glob
import json
from jsonschema import validate
import pandas as pd
import shutil
from openai import OpenAIError
from openai._exceptions import ContentFilterFinishReasonError
import concurrent.futures
import warnings


def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')


def prep_images(pdf_path):
  """Convert pdf into .jpg images."""
  # Very ungraceful use of bash
  os.makedirs("temp", exist_ok = True)
  old_files = glob.glob("temp/*")
  for file in old_files:
    os.remove(file)
  shutil.copy(pdf_path, "temp/tmp.pdf")
  os.system(f"pdftoppm -jpeg temp/tmp.pdf temp/tmp")
  pages = sorted(glob.glob("temp/tmp-*"))
  return pages


def read_util(file_name):
  """Access files from the util folder."""
  base_path = os.path.join(os.path.dirname(__file__), 'util')
  file_path = os.path.join(base_path, file_name)
  with open(file_path, 'r') as file:
    return file.read()


def transcribe_page(client, image, seed_):
  """Extract just the transcript of a single page."""
  schema_path = os.path.join(os.path.dirname(
      __file__), 'util', 'transcript_schema.json')
  with open(schema_path, 'r') as schema_file:
    schema = json.load(schema_file)
  transcribe_role = read_util('transcribe_role.txt')
  role = {"role": "system", "content": transcribe_role}
  stylized_box = read_util('stylized_box.txt')
  stylized_box_json = {
      "role": "user",
      "content": stylized_box
  }
  stylized_box_transcription = read_util('stylized_box_transcription.txt')
  stylized_box_transcription_json = {
      "role": "system",
      "content": stylized_box_transcription
  }
  transcribe_task = read_util('transcribe_task.txt')
  image_json = {
      "role": "user",
      "content": [
          {
              "type": "text",
              "text": transcribe_task
          },
          {
              "type": "image_url",
              "image_url": {
                  "url": f"data:image/jpeg;base64,{image}"
              }
          }
      ]
  }
  messages_ = [
      role,
      stylized_box_json,
      stylized_box_transcription_json,
      image_json
  ]

  attempt_call = 0 
  max_call = 10
  while True:
    try:
      response = client.beta.chat.completions.parse(
          model="gpt-4o-2024-08-06",
          messages=messages_,
          seed=seed_,
          response_format=schema
      )
      break
    except ContentFilterFinishReasonError:
      attempt_call += 1
      if attempt_call > max_call:
        warnings.warn("Too many ContentFilterFinishReasonError. These are exceptionally rare, so skipping this page.")
        return None
  return (response)

def get_info(client, pages, seed):
  """
  Uses a json schema to request information on a multipage document from 
  ChatGPT's vision API.
  """
  # Truncate if more than 100 pages. I know it's the easy way out...
  pages = pages[:100]
  info_role = read_util('info_role.txt')
  role = {"role": "system", "content": info_role}
  doc_json = {
      "role": "user",
      "content": [
      ]
  }
  for page in pages:
    image_json = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{page}"
        }
    }
    doc_json['content'].append(image_json)
  messages = [
      role,
      doc_json
  ]
  schema_path = os.path.join(os.path.dirname(
      __file__), 'util', 'info_schema.json')
  with open(schema_path, 'r') as schema_file:
    schema = json.load(schema_file)
  info = client.beta.chat.completions.parse(
      model="gpt-4o-2024-08-06",
      messages=messages,
      seed=seed,
      response_format=schema
  )
  return info


def assemble_transcript(contents):
  def assemble_one(transcript):
    assembled = transcript['final_transcript']['leftColumn']
    if transcript['final_transcript']['rightColumn']:
      assembled = assembled + '\n\n' + transcript['final_transcript']['rightColumn']
    assembled = assembled + '\n\n'
    return assembled
  assemblies = [assemble_one(content) for content in contents]
  assembled_transcript = '\n\n'.join(assemblies)
  return assembled_transcript


def get_info_by_page(contents_):
  two_columns = [content['two_columns'] for content in contents_]
  headers = [content['final_transcript']['header'] for content in contents_]
  footers = [content['final_transcript']['footer'] for content in contents_]
  left_col = [content['final_transcript']['leftColumn'] for content in contents_]
  right_col = [content['final_transcript']['rightColumn'] for content in contents_]
  transcript = [f"{left}\n\n{right}" if right is not None else left 
                for left, right in zip(left_col, right_col)]
  redaction_counts = [content['redaction_count'] for content in contents_]
  redaction_percentages = [content['redaction_percentage'] for content in contents_]
  info_by_page = pd.DataFrame({
    'page': [i for i in range(1, len(contents_) + 1)],
    'transcripts': transcript,
    'two_columns': two_columns, 
    'headers': headers,
    'footers': footers, 
    'redaction_counts': redaction_counts, 
    'redaction_percentage': redaction_percentages
    })
  return info_by_page


def get_info_overall(info_, contents):
  def concatenate(datapoints):
    if datapoints is None:
      return_value = ""
    else: 
      datapoints_sanitized = [datapoint.replace(";", ",") for datapoint in datapoints]
      return_value = ";".join(datapoints_sanitized)
    return return_value
  document_type = info_['document_type']
  if document_type == "Email chain":
    title = concatenate(info_['title'])
    date = concatenate(info_['date'])
  if document_type == "Other":
    title = info_['title']
    date = info_['date']
  redaction_terms_1 = (concatenate(set(info_['redaction_terms'])) 
                       if info_['redaction_terms'] is not None else "")
  redaction_terms_all = [content['redaction_terms'] for content in contents]
  redaction_terms_all = [elem for elem in redaction_terms_all if elem is not None]
  redaction_terms_unique = (set(element for sublist in redaction_terms_all for element in sublist)
                            if redaction_terms_all is not None else "")
  redaction_terms_2 = ';'.join(redaction_terms_unique)
  redaction_count_1 = info_['redaction_count']
  redaction_count_2 = sum([content['redaction_count'] for content in contents])
  redaction_percentage_1 = info_['redaction_percentage']
  redaction_percentage_2 = sum([content['redaction_percentage'] for content in contents]) / len(contents)
  individuals_involved = (concatenate(set(info_['individuals_involved'])) 
                          if info_['individuals_involved'] is not None else "")
  individuals_mentioned = (concatenate(set(info_['individuals_mentioned'])) 
                           if info_['individuals_mentioned'] is not None else "")
  organizations_involved = (concatenate(set(info_['organizations_involved'])) 
                            if info_['organizations_involved'] is not None else "")
  organizations_mentioned = (concatenate(set(info_['organizations_mentioned'])) 
                             if info_['organizations_mentioned'] is not None else "")
  issues = (concatenate(set(info_['issues'])) 
            if info_['issues'] is not None else "")
  info_overall = pd.DataFrame({
    'document_type': document_type,
    'title': title,
    'date': date,
    'individuals_involved': individuals_involved,
    'individuals_mentioned': individuals_mentioned,
    'organizations_involved': organizations_involved,
    'organizations_mentioned': organizations_mentioned,
    'issues': issues,
    'redaction_terms_1': redaction_terms_1,
    'redaction_terms_2': redaction_terms_2,
    'redaction_count_1': redaction_count_1, 
    'redaction_count_2': redaction_count_2,
    'redaction_percentage_1': redaction_percentage_1,
    'redaction_percentage_2': redaction_percentage_2
    }, index = [0])  
  return(info_overall)


def transcribe_and_decode(client_, pages, seed_, max_attempts=10, max_workers=16):
  def transcribe_page_with_retries(page, page_num, total_pages, client_, seed_, max_attempts):
    print(f"Transcribing page {page_num} of {total_pages}.")
    attempts = 0
    success = False
    while attempts < max_attempts and not success:
      try:
        transcript = transcribe_page(client_, page, seed_)
        if transcript is None:
            return None  # Skip if we run into exceptionally rare ContentFilterFinishReasonError
        content = json.loads(transcript.choices[0].message.content)
        success = True
        return content
      except (json.JSONDecodeError):
        attempts += 1
        print(f"{attempts} failed attempt(s) to transcribe page {page_num} of {total_pages}.")
    if not success:
      raise RuntimeError(f"Failed to transcribe page after {max_attempts} attempts.")
  
  contents = []
  total_pages = len(pages)

  with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit tasks for transcription in parallel
    future_to_page = {executor.submit(transcribe_page_with_retries, page, i, total_pages, client_, seed_, max_attempts): page for i, page in enumerate(pages, 1)}

    # Collect results as they complete
    for future in concurrent.futures.as_completed(future_to_page):
      page = future_to_page[future]
      try:
        result = future.result()
        if result is not None:
          contents.append(result)
      except Exception as exc:
        print(f"Page transcription generated an exception: {exc}")

  return(contents)


def view_doc(client, pdf, seed):
  """Handles conversion and all API calls, returns all information."""
  pages = prep_images(pdf)
  encoded_images = [encode_image(image) for image in pages]
  info = get_info(client, encoded_images, seed)
  info_parsed = json.loads(info.choices[0].message.content)['item']
  contents = transcribe_and_decode(client, encoded_images, seed)
  # transcripts = [transcribe_page(client, image, seed) for image in encoded_images]
  # contents = [json.loads(response.choices[0].message.content) for response in transcripts]
  assembled_transcript = assemble_transcript(contents)
  info_by_page = get_info_by_page(contents)
  info_overall = get_info_overall(info_parsed, contents)
  return [assembled_transcript, info_by_page, info_overall]
