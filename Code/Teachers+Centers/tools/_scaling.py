def scale_rows_to_0_1(matrix):
    """
    Takes a matrix of values and normalizes by row by using the min-max normalization
    Args:
        matrix: The bidimensional matrix of values
    Returns:
        A new matrix with the scaled values
    """
    scaled_matrix = []
    for row in matrix:
        # row = [0.5 if element == 'None' else element for element in row]
        # print(row)
        min_value = min(row)
        max_value = max(row)
        scaled_row = [(element - min_value) / (max_value - min_value) if max_value != min_value else 0.5 for element in row]
        scaled_matrix.append(scaled_row)
    return scaled_matrix