import os
import json
import concurrent.futures
from openai import AzureOpenAI
import pandas as pd
from typing import Dict, Any, List, Optional, Callable

class InvoiceAuditor:
    def __init__(self, api_key: str, endpoint: str):
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version="2024-12-01-preview",
            azure_endpoint=endpoint
        )
        self.model = "gpt-5.2-"  # Deployment name in Azure

    def _process_batch(self, chunk_pages: List[str], batch_index: int, total_batches: int, 
                      price_list_csv: str, delivery_note_text: str, custom_instructions: str, deployment_name: str) -> List[str]:
        """
        Helper function to process a single batch of pages.
        Returns a list of CSV rows found in this batch.
        """
        chunk_text = "\n--- PAGE BREAK ---\n".join(chunk_pages)
        # print(f"Processing Batch {batch_index + 1} / {total_batches} (Parallel)...") # Moved to callback
        
        system_prompt = """
        You are an expert Financial Auditor AI. Your task is to audit a PART of an invoice against a price list and delivery notes.

        🔥 PRIMARY OBJECTIVE: IDENTIFY ITEMS BILLED BUT NOT DELIVERED.

        Goal: Perform a line-by-line audit of the invoice items provided in the user input.
        
        STRICT LOGIC FOR "HANDLUNG" COLUMN:
        1. ❌ NICHT GELIEFERT (Critical):
           - If "Lieferschein-Nr" (LS-Nr) is NOT found in Delivery Note text.
           - If LS-Nr found but Article NOT on it.
           - If Quantity Delivered is 0.
        2. ❌ MENGENFEHLER: Quantity Invoiced > Delivered.
        3. ❌ PREISFEHLER: Invoice Price > Price List.
        4. ✅ OK: Correct.

        Output Format:
        Return ONLY valid JSON with this structure:
        {
            "csv_data": "Handlung;Rechnung LS-Nr;Artikel-Nr;Bezeichnung;Menge Rech;Menge Geliefert;Preis Rech;Preis Soll\\n..."
        }

        INSTRUCTIONS:
        - List EVERY single line item found in this text chunk. NO EXCEPTIONS.
        - DO NOT summarize or group items. 
        - DO NOT stop until the end of the chunk text.
        - Use semicolon (;) as separator.
        - Format numbers as standard decimals.
        - Do not include header row in csv_data if possible.
        """

        user_message = f"""
        Here is a CHUNK of the INVOICE text (Batch {batch_index + 1}):
        ---
        {chunk_text}
        ---

        Here is the PRICE LIST (Reference):
        ---
        {price_list_csv}
        ---

        Here is the DELIVERY NOTE text (optional context):
        ---
        {delivery_note_text}
        ---

        CUSTOM INSTRUCTIONS:
        {custom_instructions}

        Analyze this chunk. Return JSON with 'csv_data' containing lines for this chunk.
        """

        try:
            # Note: AzureOpenAI client is thread-safe
            response = self.client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=16000
            )
            
            content = response.choices[0].message.content
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                batch_json = json.loads(content[start:end])
                batch_csv = batch_json.get("csv_data", "")
                if batch_csv:
                    rows = batch_csv.strip().split('\n')
                    # Filter out headers if AI decided to include them despite instructions
                    rows = [r for r in rows if "Handlung" not in r and r.strip()]
                    return rows
        except Exception as e:
            print(f"Error in batch {batch_index}: {e}")
        
        return []

    def analyze_discrepancies(self,
                            invoice_data: Any,
                            price_list_csv: str,
                            delivery_note_text: str = "",
                            custom_instructions: str = "",
                            deployment_name: str = "gpt-5.2-",
                            progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """
        Sends the data to Azure OpenAI (GPT-5.2) to identify discrepancies.
        Supports Batch Processing for large invoices.
        """
        
        # Ensure invoice_data is a list of pages
        if isinstance(invoice_data, str):
            # Fallback if string passed: treat as single chunk
            pages = [invoice_data]
        else:
            pages = invoice_data

        # CHUNK CONFIGURATION
        CHUNK_SIZE = 2  # Pages per batch (Reduced to prevent truncation)
        all_csv_rows = []
        
        # Create batches
        batches = [pages[i:i + CHUNK_SIZE] for i in range(0, len(pages), CHUNK_SIZE)]
        total_batches = len(batches)
        
        # 1. PARALLEL BATCH PROCESSING
        # We use a ThreadPoolExecutor to run multiple API calls in parallel
        # Max workers = 5 to balance speed and rate limits
        completed_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Map batches to future objects
            future_to_batch = {
                executor.submit(
                    self._process_batch, 
                    batch, 
                    idx, 
                    total_batches, 
                    price_list_csv, 
                    delivery_note_text, 
                    custom_instructions, 
                    deployment_name
                ): idx 
                for idx, batch in enumerate(batches)
            }
            
            # Collect results as they complete, but store in a dict to reorder later
            results_map = {}
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                completed_count += 1
                
                # Report Progress
                if progress_callback:
                    progress_callback(completed_count, total_batches)
                
                try:
                    rows = future.result()
                    results_map[batch_idx] = rows
                except Exception as exc:
                    print(f'Batch {batch_idx} generated an exception: {exc}')
                    results_map[batch_idx] = []

        # 2. AGGREGATION (In correct order)
        for i in range(total_batches):
            if i in results_map:
                all_csv_rows.extend(results_map[i])
        
        full_csv_str = "Handlung;Rechnung LS-Nr;Artikel-Nr;Bezeichnung;Menge Rech;Menge Geliefert;Preis Rech;Preis Soll\n" + "\n".join(all_csv_rows)
        
        # 3. FINAL SUMMARY GENERATION
        result = {
            "summary": "Parallel Batch Analysis Complete. Please check the Dashboard for full details.",
            "detailed_reasoning": f"Processed {len(pages)} pages in {total_batches} parallel batches. Found {len(all_csv_rows)} line items.",
            "csv_data": full_csv_str,
            "dashboard": [
                 {"category": "GESAMT POSITIONEN", "count": len(all_csv_rows), "description": "Alle geprüften Zeilen"},
                 {"category": "ABWEICHUNGEN", "count": sum(1 for r in all_csv_rows if "OK" not in r), "description": "Alle Fehlerarten"},
                 {"category": "ÜBEREINSTIMMUNG", "count": sum(1 for r in all_csv_rows if "OK" in r), "description": "Korrekte Positionen"}
            ]
        }
        
        return result
