import os
import xml.etree.ElementTree as ET
import struct
import argparse
from pathlib import Path
import re

def extract_xml_metadata(file_path):
    """
    Extract XML metadata from a BTF file.
    
    Parameters:
    file_path (str): Path to the BTF file
    
    Returns:
    dict: Extracted metadata as a dictionary
    str: Raw XML metadata string
    """
    try:
        with open(file_path, 'rb') as f:
            # Read the entire file content
            file_content = f.read()
            
            # Method 1: Look for XML tags in the file
            # Try to find XML data using regex pattern matching
            xml_pattern = re.compile(b'<\\?xml.*?>.+?</[^>]+>', re.DOTALL)
            xml_matches = xml_pattern.findall(file_content)
            
            if xml_matches:
                # Return the first XML block found
                xml_data = xml_matches[0].decode('utf-8', errors='ignore')
                metadata_dict = parse_xml_to_dict(xml_data)
                return metadata_dict, xml_data
            
            # Method 2: Look for a specific header or marker that indicates where XML metadata begins
            # This is hypothetical and depends on your BTF format
            xml_marker = b'<XML>'
            xml_end_marker = b'</XML>'
            
            start_pos = file_content.find(xml_marker)
            if start_pos != -1:
                end_pos = file_content.find(xml_end_marker, start_pos)
                if end_pos != -1:
                    xml_data = file_content[start_pos:end_pos + len(xml_end_marker)].decode('utf-8', errors='ignore')
                    metadata_dict = parse_xml_to_dict(xml_data)
                    return metadata_dict, xml_data
            
            # Method 3: Check for a header structure that specifies XML offset and length
            # This assumes the BTF has a specific format where the XML metadata location is defined
            # in the header - you'll need to adjust this based on your actual BTF format
            
            # Example: First 4 bytes = magic number, next 4 = version, next 4 = XML offset, next 4 = XML length
            f.seek(0)
            magic = f.read(4)  # Skip magic number
            version = struct.unpack('<I', f.read(4))[0]  # Read version
            
            # Check if this looks like a valid BTF file with the expected structure
            if magic == b'BTF\0' or magic == b'BTF ' or magic == b'\0FTB' or magic == b' FTB':
                xml_offset = struct.unpack('<I', f.read(4))[0]
                xml_length = struct.unpack('<I', f.read(4))[0]
                
                # Sanity check for realistic values
                if 0 < xml_offset < os.path.getsize(file_path) and 0 < xml_length < 10000000:
                    f.seek(xml_offset)
                    xml_data = f.read(xml_length).decode('utf-8', errors='ignore')
                    
                    # Check if this looks like XML
                    if xml_data.startswith('<?xml') or xml_data.startswith('<XML>') or xml_data.startswith('<root>'):
                        metadata_dict = parse_xml_to_dict(xml_data)
                        return metadata_dict, xml_data
            
            # If we get here, we couldn't find XML metadata
            print(f"No XML metadata found in {file_path}")
            return {}, ""
            
    except Exception as e:
        print(f"Error extracting XML metadata: {e}")
        return {}, ""

def parse_xml_to_dict(xml_string):
    """
    Parse XML string to a dictionary.
    
    Parameters:
    xml_string (str): XML string to parse
    
    Returns:
    dict: Parsed XML as a nested dictionary
    """
    try:
        # Try to parse the XML
        root = ET.fromstring(xml_string)
        
        # Convert XML to dictionary
        return xml_to_dict(root)
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        
        # Try to clean the XML string if it's malformed
        cleaned_xml = clean_xml_string(xml_string)
        try:
            root = ET.fromstring(cleaned_xml)
            return xml_to_dict(root)
        except:
            print("Failed to parse XML even after cleaning")
            return {}
    except Exception as e:
        print(f"Error parsing XML: {e}")
        return {}

def clean_xml_string(xml_string):
    """
    Attempt to clean a potentially malformed XML string.
    
    Parameters:
    xml_string (str): XML string to clean
    
    Returns:
    str: Cleaned XML string
    """
    # Replace common problematic characters
    cleaned = xml_string.replace('\x00', '')
    
    # Ensure proper XML declaration
    if not cleaned.startswith('<?xml'):
        cleaned = '<?xml version="1.0" encoding="UTF-8"?>\n' + cleaned
    
    # Try to fix unclosed tags (very basic approach)
    open_tags = []
    for match in re.finditer(r'<(\w+)[^>]*>', cleaned):
        tag = match.group(1)
        open_tags.append(tag)
    
    # Add closing tags for any unclosed tags
    for tag in reversed(open_tags):
        if f'</{tag}>' not in cleaned:
            cleaned += f'</{tag}>'
    
    return cleaned

def xml_to_dict(element):
    """
    Convert an XML element to a dictionary recursively.
    
    Parameters:
    element: XML element to convert
    
    Returns:
    dict: Dictionary representation of the XML element
    """
    result = {}
    
    # Process attributes
    for key, value in element.attrib.items():
        result[f"@{key}"] = value
    
    # Process children
    for child in element:
        child_dict = xml_to_dict(child)
        
        # Handle case where a tag appears multiple times
        if child.tag in result:
            if type(result[child.tag]) is list:
                result[child.tag].append(child_dict)
            else:
                result[child.tag] = [result[child.tag], child_dict]
        else:
            result[child.tag] = child_dict
    
    # Handle text content
    if element.text and element.text.strip():
        # If we have both text and children/attributes, use #text for the text content
        if result:
            result["#text"] = element.text.strip()
        else:
            # If we only have text content, just return it directly
            return element.text.strip()
    
    return result

def save_metadata_to_file(metadata_dict, xml_data, output_path):
    """
    Save extracted metadata to files.
    
    Parameters:
    metadata_dict (dict): Dictionary of metadata
    xml_data (str): Raw XML string
    output_path (str): Base path for output files
    """
    # Save raw XML
    xml_path = f"{output_path}.xml"
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_data)
    print(f"Raw XML metadata saved to {xml_path}")
    
    # Save structured metadata as text
    txt_path = f"{output_path}.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("BTF Metadata Summary\n")
        f.write("===================\n\n")
        write_dict_to_file(f, metadata_dict)
    print(f"Formatted metadata saved to {txt_path}")

def write_dict_to_file(file, d, indent=0):
    """
    Write a dictionary to a file with indentation.
    
    Parameters:
    file: File object to write to
    d (dict): Dictionary to write
    indent (int): Current indentation level
    """
    for key, value in d.items():
        if isinstance(value, dict):
            file.write('  ' * indent + f"{key}:\n")
            write_dict_to_file(file, value, indent + 1)
        elif isinstance(value, list):
            file.write('  ' * indent + f"{key}: [list with {len(value)} items]\n")
            for i, item in enumerate(value):
                file.write('  ' * (indent + 1) + f"Item {i+1}:\n")
                if isinstance(item, dict):
                    write_dict_to_file(file, item, indent + 2)
                else:
                    file.write('  ' * (indent + 2) + f"{item}\n")
        else:
            file.write('  ' * indent + f"{key}: {value}\n")

def main():
    parser = argparse.ArgumentParser(description='Extract XML metadata from BTF files')
    parser.add_argument('input', help='Input BTF file or directory containing BTF files')
    parser.add_argument('-o', '--output', help='Output directory (optional)')
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else input_path.parent
    
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    
    if input_path.is_file():
        # Process single file
        metadata_dict, xml_data = extract_xml_metadata(str(input_path))
        if xml_data:
            output_base = output_dir / input_path.stem
            save_metadata_to_file(metadata_dict, xml_data, str(output_base))
    elif input_path.is_dir():
        # Process all BTF files in directory
        btf_files = list(input_path.glob('*.btf'))
        if not btf_files:
            print(f"No BTF files found in {input_path}")
            return
            
        print(f"Found {len(btf_files)} BTF files to process")
        for btf_file in btf_files:
            metadata_dict, xml_data = extract_xml_metadata(str(btf_file))
            if xml_data:
                output_base = output_dir / btf_file.stem
                save_metadata_to_file(metadata_dict, xml_data, str(output_base))
    else:
        print(f"Input path does not exist: {input_path}")

if __name__ == "__main__":
    main()
