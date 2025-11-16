"""
Bulk Question Processor

Handles multiple questions in a single input by:
1. Detecting bulk questions (multiple questions on separate lines or separated by ?)
2. Splitting them into individual questions
3. Processing each separately or combining intelligently
"""

import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


def split_bulk_questions(question_text: str) -> List[str]:
    """
    Split bulk questions into individual questions.
    
    Handles:
    - Multiple questions on separate lines (Shift+Enter)
    - Multiple questions separated by question marks in one line
    - Questions with different formats
    
    Args:
        question_text: Input text that may contain multiple questions
    
    Returns:
        List of individual question strings
    """
    if not question_text or not question_text.strip():
        return []
    
    question_text = question_text.strip()
    
    # Strategy 1: Split by newlines (Shift+Enter creates separate questions)
    lines = question_text.split('\n')
    
    # Filter out empty lines and clean up
    questions = []
    current_question = []
    
    for line in lines:
        line = line.strip()
        if not line:
            # Empty line - end current question if we have one
            if current_question:
                q = ' '.join(current_question).strip()
                if q:
                    questions.append(q)
                current_question = []
            continue
        
        # Check if line ends with ? (likely a complete question)
        if line.endswith('?'):
            current_question.append(line)
            q = ' '.join(current_question).strip()
            if q:
                questions.append(q)
            current_question = []
        else:
            # Check if line starts with question words (likely a new question)
            question_starters = [
                'what', 'where', 'when', 'who', 'why', 'how', 'which', 'show', 'give', 
                'list', 'tell', 'find', 'calculate', 'compare'
            ]
            line_lower = line.lower()
            starts_with_question = any(line_lower.startswith(starter) for starter in question_starters)
            
            # If current question exists and this starts a new question, save current
            if current_question and starts_with_question:
                q = ' '.join(current_question).strip()
                if q:
                    questions.append(q)
                current_question = [line]
            else:
                current_question.append(line)
    
    # Add any remaining question
    if current_question:
        q = ' '.join(current_question).strip()
        if q:
            questions.append(q)
    
    # Strategy 2: If we still have only 1 question, try splitting by multiple ? marks
    if len(questions) == 1:
        single_question = questions[0]
        # Check if there are multiple question marks (bulk question in one line)
        question_mark_count = single_question.count('?')
        if question_mark_count > 1:
            # Split by ? but keep the ? with each question
            split_questions = []
            parts = re.split(r'(\?)', single_question)
            
            current_q = ""
            for i, part in enumerate(parts):
                current_q += part
                if part == '?' and current_q.strip():
                    split_questions.append(current_q.strip())
                    current_q = ""
            
            # Add any remaining text
            if current_q.strip():
                split_questions.append(current_q.strip())
            
            if len(split_questions) > 1:
                questions = split_questions
                logger.info(f"Split bulk question into {len(questions)} questions by question marks")
    
    # Strategy 3: If still single question, check for common separators in one line
    if len(questions) == 1:
        single_question = questions[0]
        
        # Check for patterns like "What is X? What is Y? What is Z?"
        # Match sentences that start with capital letter and end with ?
        pattern = r'([A-Z][^?]*\?)'
        matches = re.findall(pattern, single_question)
        if len(matches) > 1:
            questions = [m.strip() for m in matches if m.strip()]
            logger.info(f"Split bulk question into {len(questions)} questions by pattern matching")
        
        # Also check for lowercase question starters
        elif len(questions) == 1:
            # Pattern: "what is X? what is Y? show me Z?"
            pattern2 = r'(?i)(what|where|when|who|why|how|which|show|give|list|tell|find|calculate|compare)[^?]*\?'
            matches2 = re.findall(pattern2, single_question)
            if len(matches2) > 1:
                # Extract full questions
                parts = re.split(r'((?:what|where|when|who|why|how|which|show|give|list|tell|find|calculate|compare).*?\?)', single_question, flags=re.IGNORECASE)
                questions = [p.strip() for p in parts if p.strip() and '?' in p]
                if len(questions) > 1:
                    logger.info(f"Split bulk question into {len(questions)} questions by question word pattern")
    
    # Clean up questions (remove extra spaces, ensure they end with ?)
    cleaned_questions = []
    for q in questions:
        q = re.sub(r'\s+', ' ', q.strip())  # Normalize whitespace
        if q and not q.endswith('?') and not q.endswith('.') and not q.endswith('!'):
            # Add ? if it looks like a question but doesn't end with punctuation
            question_words = ['what', 'where', 'when', 'who', 'why', 'how', 'which', 'show', 'give', 'list', 'tell']
            if any(q.lower().startswith(word) for word in question_words):
                q += '?'
        if q:
            cleaned_questions.append(q)
    
    logger.info(f"Split bulk question into {len(cleaned_questions)} individual questions")
    return cleaned_questions if cleaned_questions else [question_text]


def is_bulk_question(question_text: str) -> bool:
    """
    Check if the input contains multiple questions.
    
    Args:
        question_text: Input text to check
    
    Returns:
        True if contains multiple questions, False otherwise
    """
    if not question_text:
        return False
    
    # Check for newlines (Shift+Enter)
    if '\n' in question_text.strip():
        lines = [line.strip() for line in question_text.strip().split('\n') if line.strip()]
        if len(lines) > 1:
            return True
    
    # Check for multiple question marks
    if question_text.count('?') > 1:
        return True
    
    # Check for question starters in middle of text
    question_starters = [
        ' what ', ' where ', ' when ', ' who ', ' why ', ' how ', ' which ',
        ' show ', ' give ', ' list ', ' tell ', ' find ', ' calculate ', ' compare '
    ]
    question_lower = f' {question_text.lower()} '
    matches = sum(1 for starter in question_starters if starter in question_lower)
    
    # If we find multiple question starters, it's likely bulk
    if matches > 1:
        return True
    
    return False


def format_bulk_answer(question_answers: List[Dict[str, Any]]) -> str:
    """
    Format answers from multiple questions into a single response.
    
    Args:
        question_answers: List of dicts with 'question' and 'answer' keys
    
    Returns:
        Formatted combined answer
    """
    if not question_answers:
        return ""
    
    if len(question_answers) == 1:
        return question_answers[0]['answer']
    
    # Format as numbered list
    lines = []
    lines.append("Here are the answers to your questions:\n")
    
    for i, qa in enumerate(question_answers, 1):
        question = qa.get('question', f'Question {i}')
        answer = qa.get('answer', 'No answer available')
        
        lines.append(f"### {i}. {question}")
        lines.append("")
        lines.append(answer)
        lines.append("")
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)

