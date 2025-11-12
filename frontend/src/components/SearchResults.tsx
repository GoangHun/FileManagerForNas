import React from 'react';
import { SearchResult } from '../types';
import './SearchResults.css';

interface SearchResultsProps {
  results: SearchResult[];
  query: string;
  onClear: () => void;
}

const SearchResults: React.FC<SearchResultsProps> = ({ results, query, onClear }) => {
  return (
    <div className="search-results-container">
      <div className="search-results-header">
        <h2>Search Results for "{query}"</h2>
        <button onClick={onClear} className="clear-search-button">Back to File List</button>
      </div>
      {results.length === 0 ? (
        <p>No results found.</p>
      ) : (
        <ul className="search-results-list">
          {results.map((result) => (
            <li key={`${result.file_path}-${result.chunk_number}`} className="search-result-item">
              <div className="result-filepath">{result.file_path}</div>
              <div className="result-snippet">"{result.content_snippet}"</div>
              <div className="result-distance">
                Similarity Score: {((1 - result.distance) * 100).toFixed(2)}%
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default SearchResults;
