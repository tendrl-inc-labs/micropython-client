import json

import btree


class QueryEngine:
    """Handles query operations for the database"""
    
    @staticmethod
    def get_field_value(doc, field):
        """Get nested field value from document using dot notation"""
        if "." not in field:
            return doc.get(field)
        
        # Optimize: cache split result if field is accessed multiple times
        # (For now, just optimize the split - could add caching layer if needed)
        parts = field.split(".")
        value = doc
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
            if value is None:
                return None
        return value
    
    @staticmethod
    def matches_query(doc, query_dict):
        """Check if document matches query conditions"""
        for field, condition in query_dict.items():
            if field.startswith("$"):
                continue  # Skip special operators like $limit
                
            doc_value = QueryEngine.get_field_value(doc, field)
            
            if isinstance(condition, dict):
                # Handle operators
                for op, value in condition.items():
                    if op == "$eq":
                        if doc_value != value:
                            return False
                    elif op == "$gt":
                        if doc_value is None or doc_value <= value:
                            return False
                    elif op == "$gte":
                        if doc_value is None or doc_value < value:
                            return False
                    elif op == "$lt":
                        if doc_value is None or doc_value >= value:
                            return False
                    elif op == "$lte":
                        if doc_value is None or doc_value > value:
                            return False
                    elif op == "$in":
                        if doc_value not in value:
                            return False
                    elif op == "$ne":
                        if doc_value == value:
                            return False
                    elif op == "$exists":
                        field_exists = doc_value is not None
                        if field_exists != value:
                            return False
                    elif op == "$contains":
                        if doc_value is None:
                            return False
                        if isinstance(doc_value, str):
                            if value not in doc_value:
                                return False
                        elif isinstance(doc_value, list):
                            if value not in doc_value:
                                return False
                        else:
                            return False
            else:
                # Direct equality or array contains
                if field == "tags" or field == "_tags":
                    # Special handling for tags - check if tag is in array
                    tags = doc.get("_tags", [])
                    if condition not in tags:
                        return False
                else:
                    # Direct equality
                    if doc_value != condition:
                        return False
        return True
    
    @staticmethod
    async def execute_query(db, query_dict):
        """Execute query against database"""
        results = []
        limit = query_dict.get("$limit")
        
        try:
            keys = list(db.keys(None, None, btree.INCL))
            for key in keys:
                try:
                    key_str = key.decode()
                    raw_data = db[key]
                    doc = json.loads(raw_data.decode())
                    
                    if QueryEngine.matches_query(doc, query_dict):
                        results.append(doc)
                        if limit and len(results) >= limit:
                            break
                            
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
                    continue
                    
        except Exception as e:
            print(f"Query error: {e}")
            
        return results 