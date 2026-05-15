import hashlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.collections import PathCollection
from matplotlib.patches import Rectangle


import numpy as np
from PIL import ImageChops, Image
import io

class FigureChecker():
    def __init__(self):
        pass

    # Function to get the plot types in an axes
    def __get_plot_types(self, ax):
        plot_types = []

        for child in ax.get_children():
            if isinstance(child, plt.Line2D):
                plot_types.append('line')
            elif isinstance(child, PathCollection):
                plot_types.append('scatter')
            elif isinstance(child, Rectangle):
                break # there is always one rectangle, and I did not yet figure out what makes bar and hist rectangles unique
                # if isinstance(ax.get_xticklabels()[0].get_text()[-1], str):
                #     plot_types.append('bar')
                # else:
                #     plot_types.append('hist')
                # break
        return plot_types

    # Function to get all plot objects of a specific type from an axes
    def __get_plot_objects(self, ax, plot_type):
        if plot_type == 'line':
            return [child for child in ax.get_children() if isinstance(child, plt.Line2D)]
        elif plot_type == 'scatter':
            return [child for child in ax.get_children() if isinstance(child, PathCollection)]
        elif plot_type in ('bar', 'hist'):
            return [child for child in ax.get_children() if isinstance(child, Rectangle)]
        else:
            raise ValueError("Unsupported plot type. Use 'line', 'scatter', 'bar', or 'hist'.")

    def identical_figures(self, fig1: str|Figure, fig2: str|Figure) -> bool:
        if isinstance(fig1, Figure):
            buf1 = io.BytesIO()
            fig1.savefig(buf1, format='png')
            buf1.seek(0)
            source1 = buf1
        else:
            source1 = fig1 

        if isinstance(fig2, Figure):
            buf2 = io.BytesIO()
            fig2.savefig(buf2, format='png')
            buf2.seek(0)
            source2 = buf2
        else:
            source2 = fig2

        # Load the images from the buffers
        img1 = Image.open(source1).convert('L')  # Convert to grayscale
        img2 = Image.open(source2).convert('L')  # Convert to grayscale

        # Compare the images
        diff = ImageChops.difference(img1, img2)

        return diff.getbbox() is None

    # Method to compare plot properties
    def compare_plots(self, ax1, ax2, plot_diff: bool = False):
        types1, types2 = self.__get_plot_types(ax1), self.__get_plot_types(ax2)

        assert types1 == types2 , f'plots have not the same (amount of) types: "{types1}" and "{types2}"'
        for type1, type2 in zip(types1, types2):
            objects1, objects2 = self.__get_plot_objects(ax1, type1), self.__get_plot_objects(ax2, type2)    

            assert len(objects1) == len(objects2) , f'"{type1}" and "{type2}" have a different number of plot objects: {len(objects1)} vs {len(objects2)}'
            plots = []
            for obj1, obj2 in zip(objects1, objects2):
                plots.append(self.__compare_properties(type1, obj1, obj2))

                if plot_diff and (type1 != 'bar' or obj1 == objects1[-1]):
                    self.__plot_diff(type1, obj1, obj2, objects1, objects2)
                i+=1       
            return plots
        
    def __compare_properties(self, type1, obj1, obj2) -> dict:
        res = {}
        if type1 in ('bar', 'hist'):
            res['color'] = obj1.get_facecolor() == obj2.get_facecolor()
            res['marker']  = 'n/a' if type1 in ('bar', 'hist') else obj1.get_paths()[0].vertices == obj2.get_paths()[0].vertices
            res['label'] = 'n/a' if type1 in ('bar', 'hist') else obj1.get_label()
        elif type1 == 'scatter':
            res['color'] = bool((obj1.get_facecolor() == obj2.get_facecolor()).all())
            res['marker']  = bool((obj1.get_paths()[0].vertices == obj2.get_paths()[0].vertices).all())
            res['label'] = obj1.get_label() == obj2.get_label()
        else:
            for prop in ['label', 'color', 'marker']:
                    res[prop] = getattr(obj1, 'get_' + prop)() == getattr(obj2, 'get_' + prop)()
        comp = {type1: res}            
        return comp

    def __plot_diff(self, type1, obj1, obj2, objects1, objects2) -> None:
        if type1 == 'line':
            x = obj1.get_xdata()
            y_diff = obj2.get_ydata() - obj1.get_ydata()
            _ , ax_diff = plt.subplots()
            ax_diff.plot(x, y_diff, label='Line difference: ax1 -> ax2', color= obj1.get_color())
            ax_diff.legend()  
        elif type1 == 'scatter':
            x = obj1.get_offsets()[:, 0]
            y_diff = obj2.get_offsets()[:, 1] - obj1.get_offsets()[:, 1]
            _ , ax_diff = plt.subplots()
            ax_diff.scatter(x, y_diff, label='Scatter difference: ax1 -> ax2', color= obj1.get_facecolor())
            ax_diff.legend()  
        elif type1 == 'bar':
            x = [bar.get_x() + bar.get_width() / 2 for bar in objects1]
            y_diff = [bar2.get_height() - bar1.get_height() for (bar1,bar2) in zip(objects1, objects2)]
            _ , ax_diff = plt.subplots()
            ax_diff.bar(x, y_diff, label='bar Difference: ax1 -> ax2', color= obj1.get_facecolor())
            ax_diff.legend()  
        elif type1 == 'hist':
            raise NotImplementedError
        plt.show()

    # Previous version with the problem that png has a compression
    # @staticmethod
    # def hash(fig: Figure) -> str:
    #     buf = io.BytesIO()
    #     fig.savefig(buf, format='png')
    #     buf.seek(0)
    #     img = Image.open(buf).convert('L') 
    #     img_bytes = img.tobytes()

    #     md5_hash = hashlib.md5()
    #     md5_hash.update(img_bytes)
    #     return md5_hash.hexdigest()

    @staticmethod
    def hash(fig: Figure, downscale_size=(200, 200)) -> str:
        """
        Generate a robust hash for a matplotlib Figure.
        - Normalizes figure rendering.
        - Converts to grayscale.
        - Optionally downsamples to reduce sensitivity to tiny pixel differences.
        """
        # Force rendering of the figure
        fig.canvas.draw()
        
        # Get RGB buffer as numpy array
        width, height = fig.canvas.get_width_height()
        img_array = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        img_array = img_array.reshape((height, width, 3))
        
        # Convert to grayscale using standard luminance formula
        img_gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
        
        # Optional: downscale for robustness
        if downscale_size is not None:
            img_gray = np.array(Image.fromarray(img_gray).resize(downscale_size, resample=Image.BILINEAR))
        
        # Hash the grayscale bytes
        md5_hash = hashlib.md5(img_gray.tobytes())
        return md5_hash.hexdigest()
    
    def compare_with_hash(self, fig: Figure, hash: str):
        fig_hash = self.hash(fig)
        return fig_hash == hash





if __name__ == '__main__':

    # x = [1, 2, 3, 4, 5]
    # y = [2, 3, 5, 7, 11]
    # a = [2, 9, 2, 7, 11]


    # fig1, ax1 = plt.subplots()
    # fig2, ax2 = plt.subplots()

    # ax1.plot(x, y) # line
    # ax2.plot(x, a) # line

    # ax1.scatter(x, y, label='hello') # scatter
    # ax2.scatter(x,a, label='hello')

    # x = ['A', 'B', 'C', 'D', 'E']
    # z = ['1', '2', '3', '4', '5']
    # ax1.bar(x, y, label='Values')
    # ax2.bar(x, y, label='Values1')


    # data = [1, 2, 2, 3, 3,4,1]
    # ax1.hist(data, bins=3)
    # ax2.hist(data, bins=4)

    # ax1 = ax2 = ax

    # Create two different plots
    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)

    fig1, ax1 = plt.subplots()

    ax1.plot(x, y1, label='Sine Wave', color='blue', marker='o')
    # fig1.savefig('plot1.png')

    y2 = np.cos(x)
    # y2 = np.sin(x)

    fig2, ax2 = plt.subplots()
    ax2.plot(x, y2)
    # fig2.savefig('plot2.png')

    checker = FigureChecker()

    print('Hash:', checker.hash(fig1))
    print('Identical hash:', checker.compare_with_hash(fig1, 'b4ece5c700beaf8b2053e4f856c0b549'))
    # print(checker.identical_figures(fig2, fig2))
    # print(checker.identical_figures(fig1, 'plot1.png'))
    # print(checker.compare_plots(ax1, ax2, True))
