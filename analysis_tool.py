# Import necessary packages
import os
import requests
import chardet  # To detect the encoding of the HTML files
import datetime
import time
from multiprocessing import Pool
import sys
import json
import re
import pandas as pd
import random
from bs4 import BeautifulSoup

#Red API KEY Value from openaikeys.txt, each line in the file is a key
def get_api_key():
    global API_KEY
    with open("openaikeys.txt") as f:
        API_KEY = f.readlines()
        return API_KEY
#set API_KEY to a random key from the list of keys
API_KEY = random.choice(get_api_key()).strip()
# Path to the folder containing the domain folders
PATH = os.getcwd()

# Dictionary to store the extracted information
data = {}
# Function to retrieve the content of a HTML file
def get_html_content(file_path):
    
    # Create a list of all charsets 
    charset = chardet.detect(open(file_path, 'rb').read())['encoding']
    # Try to open the file with the current charset
    try:
        with open(file_path, encoding=charset) as f:
            content = f.read()
            # Use BeautifulSoup to parse the content and remove unnecessary whitespace
            soup = BeautifulSoup(content, 'html.parser')
            content = soup.prettify()
    # Set the encoding to utf-8 if no encoding was detected
    except:
        encoding = "utf-8"
        with open(file_path, "r", encoding = encoding) as f:
            content = f.read()
            # Use BeautifulSoup to parse the content and remove unnecessary whitespace
            soup = BeautifulSoup(content, 'html.parser')
            content = soup.prettify()
            # Print no encoding detected for domain
            print("No encoding detected on domain: " + file_path + " using utf-8 as default encoding")
    return content

# Function to split the HTML content into manageable chunks
def split_content(html_content):
    if html_content is None:
        raise ValueError("html_content is None, cannot split")
    # Split the HTML content into manageable chunks
    chunks = [html_content[i:i + 3500]
              for i in range(0, len(html_content), 3500)]
    return chunks

# Function to send the HTML content to OpenAI and retrieve the response
def send_to_openai(html_content):
    global API_KEY
    global response
    url = 'https://api.openai.com/v1/completions'

    data = {
        'model': 'text-davinci-003',
        'prompt': html_content + " Analyse the HTML code above and write a detailed analysis about it." + \
        "The analysis should be brief and it should be in this format:" + \
        "Plugins: list of  plugins and used APIs. " + \
        "Frameworks: list of frameworks used and a brief of what each framework does and whether the framework is outdated or not File hashes used:" + \
        "License information:" + \
        "Vulnerability and security issues: should include a list of vulnerabilities and a detiled brief about influences behind those issues, should also include a list of illegal javascripts, other security issues like use of weak passwords and poor encryption." + \
        "Poor practices: a list of poor coding practices being used and detailed influences behind those practices",
        'max_tokens': 300,
        'temperature': 0.7,
        'top_p': 1
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(API_KEY)
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        #Check for rate limit exceeded error
        if err.response.status_code == 429 or err.response.status_code == 401:
            #Read API_KEY from openaikeys.txt
            with open("openaikeys.txt") as f:
                API_KEY = f.readlines()
                # Check if there are more API keys available
                if len(API_KEY) > 1:
                    API_KEY.pop(0)
                    API_KEY = random.choice(API_KEY).strip()
                    print("Rate limit exceeded while using {API_KEY}, using a new API key")
                    headers = {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer {}'.format(API_KEY)
                    }
                    response = requests.post(url, json=data, headers=headers)
                    return response.json()
                else:
                    #Allow user to enter API_KEY
                    user_input = input("Enter other API keys seperated by commas: ")
                    user_input = re.split('[, ]', user_input)
                    #Write the new API_KEY to openaikeys.txt
                    with open('openaikeys.txt', 'w') as f:
                          for item in user_input:
                            f.write("%s," % item)
                    API_KEY = open("openaikeys.txt").readlines()[0].strip()
                    headers = {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer {}'.format(API_KEY)
                    }
                    print("Rate limit exceeded, using a new API key")
                    response = requests.post(url, json=data, headers=headers)
                    return response.json()
        else:
            print("response is invalid")
            print("error code: " + str(err.response.status_code))
            return None
        
# Function to extract the desired information from the OpenAI response
def extract_information(openai_response):
    # Check if the response is valid and contains the required data
    if openai_response and "choices" in openai_response:
        # Extract the plugins and frameworks from the response
        data = openai_response["choices"][-1]["text"]

        return data

# Function to write the extracted information to a markdown file
def write_to_file(data, domain):
     
    # Create the file if it doesn't already exist
    if not os.path.exists(os.path.join(PATH, domain, 'domainanalysis.md')):
        with open(os.path.join(PATH, domain, 'domainanalysis.md'), "w", encoding="utf-8") as f:
            open(os.path.join(PATH, domain, 'domainanalysis.md'), "w").close()

    # Append the analysis report of the domain to the file
    with open(os.path.join(PATH, domain, 'domainanalysis.md'), "a", encoding="utf-8") as f:
        f.write(f"# Analysis of {domain}\n\n")
        f.write(str(data))


# Function to read the success.txt file and grab the domain names
def read_success_file():
    with open("success.txt") as f:
        content = f.read()
        domain_names = content.splitlines()
    return domain_names

# Function to calculate and display the progress
def display_progress(domain_names, domain_names_done):
    total_domains = len(domain_names)
    domains_done = len(domain_names_done)
    progress_percentage = (domains_done/total_domains) * 100
    time_remaining = (total_domains - domains_done) * 5
    print(f"{domains_done}/{total_domains} domains processed ({progress_percentage:.2f}%) - {time_remaining:.2f}s remaining")

# Function to be used by the Pool object
# Function to be used by the Pool object
def process_domain(domain):
    global html_chunks
    global chunk
    print(f"starting analysis of {domain}")
    # Check if the given path is a directory
    if os.path.isdir(os.path.join(PATH, domain)):
        # Retrieve the content of the HTML files
        for file in os.listdir(os.path.join(PATH, domain)):
            html_content = get_html_content(os.path.join(PATH, domain, file))

        # Split the HTML content into manageable chunks
        html_chunks = split_content(html_content)
        # print(f"{len(html_chunks)} chunks created for {domain}")

        # Send each chunk to OpenAI and retrieve the response
        progress_data = {}
        for chunk in html_chunks:
            print(f"working on chunk {html_chunks.index(chunk)} of {domain}")
             # If the length of the HTML chunks is greater than 10, generate a list of random indices and send chunks to OpenAI
            if len(html_chunks) > 10:
                rand_indices = random.sample(range(1, len(html_chunks)-1), 6)
                for index in rand_indices:
                    openai_response = send_to_openai(html_chunks[index])
            else:
                openai_response = send_to_openai(chunk)

            openai_response = send_to_openai(chunk)
            print(f"succesffuly posted chunk {html_chunks.index(chunk)} of {domain} to openai")


            if openai_response is not None:
                # Extract the desired information from the OpenAI response
                data = extract_information(openai_response)

                # Write the extracted information to a markdown file
                write_to_file(data, domain)
                # Append a statement in a file called analysed.txt
                with open('analysed.txt', 'a') as f:
                    f.write(f'{domain} successfully analysed on {datetime.datetime.now()}\n')
                print (f"{domain} successfully analysed and saved on {datetime.datetime.now()}")
                # Save the progress of the current domain
                progress_data[domain] = {
                  'chunks_created': len(html_chunks),
                  'chunk_index': html_chunks.index(chunk)
                }
        return domain, progress_data

# Dictionary to store the progress of each domain
progress_data = {}

def freeze_support():
    """This function is used to enable support for running Python code
    in a frozen application.
    """
    pass

if __name__ == '__main__':
  freeze_support()
  # Loop through the domain folders
  domain_names = read_success_file()
  domain_names_done = []
  print("Starting analysis process... of " + str(len(domain_names)) + " domains")
  start_time = time.time()
  #Read API_KEY from openaikeys.txt
  with open("openaikeys.txt") as f:
        API_KEY = f.readlines()[0].strip()
  # Use a Pool object to apply the process_domain function to each domain
  with Pool(9) as p:
      for domain in p.imap_unordered(process_domain, domain_names):
          domain_names_done.append(domain)
          display_progress(domain_names, domain_names_done)
          # Save the progress of the current domain

  # Calculate the time taken to complete the process
  time_taken = time.time() - start_time

  # Output the total time taken
  print(f"Analysis process completed in {time_taken:.2f}s")
  print("Analysis reports written to the analysis.md file in each domain folder")
  # Save the progress data to the progress.json file
  with open('progress.json', 'w') as f:
      json.dump(progress_data, f, indent=4)
  #Allow user to enter API_KEY
  try:
      if response.status_code == 429 or response.status_code == 401:
            user_input = input("Enter other API keys seperated by commas: ")
            user_input = re.split('[, ]', user_input)
            #Write the new API_KEY to openaikeys.txt
            with open('openaikeys.txt', 'w') as f:
                  for item in user_input:
                    f.write("%s," % item)
  except:
      pass