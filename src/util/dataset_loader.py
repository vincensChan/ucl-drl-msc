from pymongo import MongoClient
import argparse
import pandas
import os
import time
import gensim
import numpy as np
import json

parser = argparse.ArgumentParser(description='Process Dataset for RS environment.')
parser.add_argument('dataset', type=str, help='Dataset schema to load (e.g. Movielens or Netflix)')
parser.add_argument('url', type=str, help='Directory to dataset files')
parser.add_argument('--create-tmatrix', default=False, help='Whether to create or load the transition matrix.')
parser.add_argument('--save-dat-file', default=False, help='Store rating matrix with item feature vector in the filesystem')

datafiles = {"movielens100k": {"trmatrix": {"filename": "trmatrix",
                                           "column_names": ["_id", "count"],
                                           "separator": "\\t", "header": None
                                           },
                               "items": {"filename": "u.item",
                                         "column_names": ["_id", "embeddings", "release_date", "video_rdate", "IMDb",
                                                          "unknown", "action", "adventure", "animation", "child",
                                                          "comedy", "crime", "documentary", "drama", "fantasy",
                                                          "film-noir", "horror", "musical", "mistery", "romance",
                                                          "sci-fi", "thriller", "war", "western"],
                                         "combined_feat": ["unknown", "action", "adventure", "animation", "child",
                                                          "comedy", "crime", "documentary", "drama", "fantasy",
                                                          "film-noir", "horror", "musical", "mistery", "romance",
                                                          "sci-fi", "thriller", "war", "western"],
                                         "separator": "|", "header": None
                                         },
                               "ratings": {"filename": "u.data",
                                           "column_names": ["user_id", "item_id", "rating", "timestamp"],
                                           "separator": "\t", "header": None
                                           }
                               },
             "movielens1m": {
                 # "trmatrix": {"filename": "trmatrix",
                 #                           "column_names": ["_id", "count"],
                 #                           "separator": "\\t", "header": None
                 #                           },
                               "items": {"filename": "movies.fixed.dat",
                                         "column_names": ["_id", "embeddings", "unknown", "action", "adventure",
                                                          "animation", "children's",
                                                          "comedy", "crime", "documentary", "drama", "fantasy",
                                                          "film-noir", "horror", "musical", "mistery", "romance",
                                                          "sci-fi", "thriller", "war", "western"],
                                         "combined_feat": ["unknown", "action", "adventure", "animation", "children's",
                                                          "comedy", "crime", "documentary", "drama", "fantasy",
                                                          "film-noir", "horror", "musical", "mistery", "romance",
                                                          "sci-fi", "thriller", "war", "western"],
                                         "separator": "|", "header": None
                                         },
                               "ratings": {"filename": "ratings.fixed.dat",
                                           "column_names": ["user_id", "item_id", "rating", "timestamp"],
                                           "separator": "::", "header": None
                                           }
                               }
             }

class Dataset_Loader(object):

    def __del__(self):
        self.client.close()

    def __init__(self, collection, url, create_trans_matrix=True, save_dat_file=False):
        self.dataset_dir = url
        self.client = MongoClient()
        # Database
        self.db = self.client['recommender']
        self.collection_suffix = str.lower(collection.strip())
        if create_trans_matrix:
            self.word_embeddings(save_dat_file)
            # self.create_transition_matrix() # TODO: no longer needed ?
            # self.save_ratings() # TODO: no longer needed ?

    # def create_transition_matrix(self):
    #     dataset = datafiles[self.collection_suffix]['ratings']
    #     data = self.read_csv_data(dataset['filename'], separator=dataset['separator'],
    #                               column_names=dataset['column_names'], header=dataset['header'])
    #     data = data.sort(columns=["user_id", "timestamp"])
    #     users = data["user_id"].unique()
    #     counts = {}
    #     start_time = time.time()
    #     for user in users:
    #         prev_s = None
    #         prev_timestamp = None
    #         for _, row in data[data["user_id"] == user].iterrows():
    #             assert prev_timestamp is None or prev_timestamp <= row["timestamp"], \
    #                 "User items are not ordered chronologically"
    #             item = row["item_id"]
    #             if prev_s is not None:
    #                 key = str(prev_s) + '|' + str(item)
    #                 counts[key] = 0 if key not in counts.keys() else counts[key] + 1
    #                 counts[prev_s] = 0 if prev_s not in counts.keys() else counts[prev_s] + 1
    #                 # add same count with inverted index for items that have been selected at the same timestamp
    #                 if prev_timestamp == row["timestamp"]:
    #                     key = str(item) + '|' + str(prev_s)
    #                     counts[key] = 0 if key not in counts.keys() else counts[key] + 1
    #             prev_s = str(item)
    #             prev_timestamp = row["timestamp"]
    #     print('Elapsed time: {} min'.format( ((time.time() - start_time)/60000)) )
    #     print(len(counts.keys()))

    def word_embeddings(self, save_dat_file):
        """

        :param save_dat_file:
        :return:
        """
        class MySentences(object):
            def __init__(self, data_frame):
                self.data_frame = data_frame

            def __iter__(self):
                for _, row in self.data_frame.iteritems():
                    yield row

        table_name = 'items'
        data_set = datafiles[self.collection_suffix][table_name]
        data = self.__read_csv_data(table_name).sort_values(by=['_id'])
        raw_sentences = data['embeddings'].str.replace("\\(|\\)","").str.split(' ')
        sentences = MySentences(raw_sentences)
        start_time = time.time()
        word2vec = gensim.models.Word2Vec(sentences, window=10, min_count=1, workers=4, sample=0.001)
        word2vec.save_word2vec_format("../../data/word2vec-" + self.collection_suffix + ".model", binary=False)
        print('word2vec finished in {} seconds'.format(time.time() - start_time))

        data['embeddings'] = raw_sentences.apply(lambda x: np.sum(word2vec[x], axis=0))
        # data['other_feat'] = data[data_set['combined_feat']].apply(lambda x: [x.values], axis=1)
        data['other_feat'] = [row for row in data[data_set['combined_feat']].values]

        if not save_dat_file: # TODO: implement else condition
            # Collection
            collection = self.db['items_' + self.collection_suffix]
            # sample = collection.find_one()
            rs = collection.delete_many({})
            print('Items Deleted: {}'.format(rs.deleted_count))
            records = json.loads( data[['_id', 'embeddings', 'other_feat']].T.to_json() ).values()
            result = collection.insert_many(records)
            print(result)
        else:
            rows = []
            for row in data[['_id', 'embeddings', 'other_feat']].values:
                rows.append(np.hstack((row[0], row[1], row[2])))
            np.savetxt("../../data/embeddings-" + self.collection_suffix + ".csv", rows, fmt="%.19f", delimiter=",")
            print "Embeddings successfully saved in the filesystem"
            data[['_id', 'embeddings', 'other_feat']].to_csv('../../data/items_collection.csv')

    def create_transition_matrix(self):
        """

        :return:
        """
        table_name = 'trmatrix'
        data_set = datafiles[self.collection_suffix][table_name]
        data = self.__read_csv_data(table_name).sort(['_id'])

        # Collection
        collection = self.db[table_name + '_' + self.collection_suffix]
        # sample = collection.find_one()
        rs = collection.delete_many({})
        print('Transition matrix -> {} records deleted'.format(rs.deleted_count))
        records = json.loads(data[data_set['column_names']].T.to_json()).values()
        result = collection.insert_many(records)


        # # dataset = datafiles[self.collection_suffix]['ratings']
        # data = self.__read_csv_data('ratings')
        # # data = self.read_csv_data(dataset['filename'], separator=dataset['separator'],
        # #                           column_names=dataset['column_names'], header=dataset['header'])
        # # data = data.sort(columns=["user_id", "timestamp"])
        # # users = data["user_id"].unique()
        # counts = {}
        # start_time = time.time()
        # # for user in users:
        # #     prev_s = None
        # #     prev_timestamp = None
        # for _, row in data.iterrows():
        #     # assert prev_timestamp is None or prev_timestamp <= row["timestamp"], \
        #     #     "User items are not ordered chronologically"
        #     item1 = str(row["item_id1"])
        #     item2 = str(row["item_id2"])
        #     key = item2 + '|' + item1 if item2 != 'nan' and len(item2) > 0 else item1
        #     counts[key] = 0 if key not in counts.keys() else counts[key] + 1
        #     # counts[prev_s] = 0 if prev_s not in counts.keys() else counts[prev_s] + 1
        #     # add same count with inverted index for items that have been selected at the same timestamp
        #     if row["timestamp1"] == row["timestamp2"]:
        #         key = item1 + '|' + item2
        #         counts[key] = 0 if key not in counts.keys() else counts[key] + 1
        #
        #     # if prev_s is not None:
        #     #     key = str(prev_s) + '|' + str(item)
        #     #     counts[key] = 0 if key not in counts.keys() else counts[key] + 1
        #     #     counts[prev_s] = 0 if prev_s not in counts.keys() else counts[prev_s] + 1
        #     #     # add same count with inverted index for items that have been selected at the same timestamp
        #     #     if prev_timestamp == row["timestamp"]:
        #     #         key = str(item) + '|' + str(prev_s)
        #     #         counts[key] = 0 if key not in counts.keys() else counts[key] + 1
        #     # prev_s = str(item)
        #     # prev_timestamp = row["timestamp"]
        # print('Elapsed time: {} min'.format(((time.time() - start_time) )))
        # print(len(counts.keys()))

    def save_ratings(self):
        table_name = 'ratings'
        data_set = datafiles[self.collection_suffix]['ratings']
        data = self.__read_csv_data(table_name).sort_values(by=['user_id', 'timestamp'])
        # Collection
        collection = self.db[table_name + '_' + self.collection_suffix]
        # sample = collection.find_one()
        rs = collection.delete_many({})
        print('User Ratings -> {} records deleted'.format(rs.deleted_count))
        records = json.loads(data[data_set['column_names']].T.to_json()).values()
        result = collection.insert_many([r for r in records])



    # def __read_csv_data(self, filename, separator="\\t", column_names=None, header=None):
    def __read_csv_data(self, table_name):
        data_set = datafiles[self.collection_suffix][table_name]
        return pandas.read_csv(os.path.join(self.dataset_dir, data_set['filename']), sep=data_set['separator'],
                                  names=data_set['column_names'], header=data_set['header'])
        # return pandas.read_csv(os.path.join(self.dataset_dir,filename), sep=separator, names=column_names, header=header)




if __name__ == '__main__':
    # example parameters to run: --create-tmatrix True movielens100k    /Users/santteegt/Downloads/ml-100k
    args = parser.parse_args()
    loader = Dataset_Loader(args.dataset, args.url, args.create_tmatrix, args.save_dat_file)
