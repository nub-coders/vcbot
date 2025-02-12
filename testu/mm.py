def convert_to_html(text, msg_entities):
            # Convert entities to a list of (position, tag, is_opening) tuples
            tag_positions = []
            
            for entity in msg_entities:
                # Get entity type from the entity object
                entity_type = entity.type
                
                if entity_type in ENTITY_TO_HTML:
                    start_tag, end_tag = ENTITY_TO_HTML[entity_type]
                    
                    # Handle pre tag with language
                    if entity_type == MessageEntityType.PRE and hasattr(entity, 'language') and entity.language:
                        tag_positions.append((entity.offset, f'<pre language="{entity.language}">', True))
                    else:
                        tag_positions.append((entity.offset, f'<{start_tag}>', True))
                    
                    tag_positions.append((entity.offset + entity.length, f'</{end_tag}>', False))

            # Sort positions, putting closing tags before opening tags at the same position
            tag_positions.sort(key=lambda x: (x[0], x[2]))
            
            # Build the final text with HTML tags
            result = []
            current_pos = 0
            
            for pos, tag, _ in tag_positions:
                if pos > current_pos:
                    result.append(text[current_pos:pos])
                result.append(tag)
                current_pos = pos
            
            if current_pos < len(text):
                result.append(text[current_pos:])
                
            return ''.join(result)
