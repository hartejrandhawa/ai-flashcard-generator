// Keep MAX_NOTES_CHARS in sync with MAX_NOTES_CHARS in backend/lambda_functions/generate_flashcards.py.
export const MAX_NOTES_CHARS = 50_000;
export const MAX_DECK_NAME_CHARS = 100;
export const MAX_FILE_BYTES = 20 * 1024 * 1024;
// Stop extracting a PDF once it is clearly over the limit; the user must trim it anyway.
export const MAX_EXTRACT_CHARS = MAX_NOTES_CHARS * 2;
