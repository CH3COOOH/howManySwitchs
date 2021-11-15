import copy
import sys
import json

BUILD = '20211110'

class Switch():
	## 引数：SWポート総数、使用可能IF数[1]、同様な仕様が重複使用できるかどうか[2]
	## [1] UplinkやPort-Channelを繋げるために、全てのIFが使えるわけではない
	## [2] 重複使用できるのは新規追加のSWのみ
	def __init__(self, nPort_nIdle, reusable=False):
		self.nPort = nPort_nIdle[0]
		self.nIdle = nPort_nIdle[1]
		self.nUnavailable = self.nPort - self.nIdle
		self.isUsed = False
		self.isReusable = reusable
		self.isAvailable = True

	def renew(self):
		self.nIdle = self.nPort - self.nUnavailable
		self.isUsed = False

	def plugin(self, n):
		if self.nIdle < n:
			return -1
		self.nIdle -= n
		self.isUsed = True
		return 0

	def isFull(self):
		if self.nIdle == 0:
			if self.isReusable == False:
				self.isAvailable = False
			return True
		if self.nIdle < 0:
			print('*** Port Error ***')
			if self.isReusable == False:
				self.isAvailable = False
			return True

class SwitchPool:
	## 引数：プール名、既存SWリスト、新規追加用SW
	def __init__(self, label, start_sw, real_sw):
		self.label = label		# プール名
		self.nFullyUsed = 0		# 全てのIFが利用されたSWの数
		self.poolSw = real_sw		# 新規追加のSW
		self.poolExistedSwitchs = start_sw		# DC中既存のSWリスト
		self.isUsingExisted = True		# 	既存SWを利用しているかどうか
		self.currentSw = start_sw[0]		# まず既存SWリストの一番を利用する
		
		print('=== 既存＜%s＞情報 ===' % self.label)
		for i in range(len(self.poolExistedSwitchs)):
			print('%d号機：IF総数=%d、余剰IF=%d' % (i+1, self.poolExistedSwitchs[i].nPort, self.poolExistedSwitchs[i].nIdle))
		
		print('既存＜%s＞(%d/%d)使用中。' % (self.label, self.currentSw.nIdle, self.currentSw.nPort))
	
	def plugin(self, n, hard=True):
		## hard: IFが不足の場合、余剰IFがあっても使用しない。（Leaf用）
		if self.currentSw.plugin(n) == -1:
			self.nFullyUsed += 1
			n_delta = n - self.currentSw.nIdle  ## hardを使わないとこの変数が無効
			if self.currentSw.isReusable == True:
				self.currentSw = copy.copy(self.poolSw)
				print('😨新しい＜%s＞が追加された。現在、＜%s＞%d台は既に利用済み。' % (self.label, self.label, self.nFullyUsed))
			else:
				if self.nFullyUsed == len(self.poolExistedSwitchs):
					print('*** 全ての既存＜%s＞が利用済み。新規追加を利用する。' % self.label)
					self.currentSw = copy.copy(self.poolSw)
					self.isUsingExisted = False
				else:
					self.currentSw = self.poolExistedSwitchs[self.nFullyUsed]
					print('*** 既存＜%s＞がダメ🙅になった。次の＜%s＞(%d/%d)を使用する。' % (self.label, self.label, self.currentSw.nIdle, self.currentSw.nPort))
			if hard == False:
				# IFが不足の場合、使用中のSWのIFを全部使用してから次のSWに切り替える
				self.currentSw.plugin(n_delta)
			else:
				# IF基本はLeaf用（余剰IF数が≧2を確保必要）
				self.currentSw.plugin(n)
			return -1
		return 0

	def getPoolInfo(self):
		return {'label': self.label, 'used': self.nFullyUsed - len(self.poolExistedSwitchs) + 1} 

	def getCurrentInfo(self):
		nPortAvailable = self.currentSw.nPort - self.currentSw.nUnavailable
		nPortUsed = nPortAvailable - self.currentSw.nIdle
		return (nPortUsed, nPortAvailable)


class Tsukuba:
	def __init__(self, leafPool, mgmtPool):
		# self.leafPool = SwitchPool('Leaf（2台組）', [Switch(96, 68), Switch(96, 74), Switch(96, 62)], Switch(96, 88, True))
		# self.mgmtPool = SwitchPool('Mgmt', [Switch(48, 5), Switch(48, 7)], Switch(48, 46, True))
		self.leafPool  = leafPool
		self.mgmtPool = mgmtPool

	def newServerPlugin(self):
		if self.leafPool.plugin(6) == -1:
			self.__event_newLeafPlugin()
		if self.mgmtPool.plugin(1, False) == -1:
			self.__event_newMgmtPlugin()

	def __event_newLeafPlugin(self):
		## 1 leaf group uses 4 mgmt ports:
		## ZTP * 2
		## Mgmt * 2
		if self.leafPool.isUsingExisted == False:
			print('*** 追加Leafが、MgmtにZTP*2+Mgmt*2を占用する。')
			if self.mgmtPool.plugin(4, False) == -1:
				print('*** Leaf追加によりMgmt枯渇が発生。')
				self.__event_newMgmtPlugin()

	def __event_newMgmtPlugin(self):
		## 1 mgmt uses 2 leaf group ports
		## Communication * 2
		if self.mgmtPool.isUsingExisted == False:
			print('*** 追加Mgmtが、LeafにアクセスIF*2を占用する。')
			if self.leafPool.plugin(2) == -1:
				print('*** Mgmt追加によりLeaf枯渇が発生。')
				self.__event_newLeafPlugin()

	def showPools(self):
		self.leafPool.showInfo()
		self.mgmtPool.showInfo()

	def showPoolInfo(self):
		dic_leaf = self.leafPool.getPoolInfo()
		dic_mgmt = self.mgmtPool.getPoolInfo()
		print('＜%s＞%d台が追加必要。' % (dic_leaf['label'], dic_leaf['used']))
		print('＜%s＞%d台が追加必要。' % (dic_mgmt['label'], dic_mgmt['used']))

def readSwitchPoolFromJson(jConfig):
	ex_leaf = jConfig['LEAF_GR']['existed']
	de_leaf = jConfig['LEAF_GR']['default']
	sw_ex_leaf = []
	for info in ex_leaf:
		sw_ex_leaf.append(Switch(info))
	leafPool = SwitchPool('LEAF_GR', sw_ex_leaf, Switch(de_leaf, True))
	
	ex_mgmt= jConfig['MGMT']['existed']
	de_mgmt = jConfig['MGMT']['default']
	sw_ex_mgmt = []
	for info in ex_mgmt:
		sw_ex_mgmt.append(Switch(info))
	mgmtPool = SwitchPool('MGMT', sw_ex_mgmt, Switch(de_mgmt, True))
	return leafPool, mgmtPool

def main():
	N_SRV = int(sys.argv[1])
	jSwitchePools = json.load(open(sys.argv[2], 'rb'))
	lp, mp = readSwitchPoolFromJson(jSwitchePools)
	datacenter = Tsukuba(lp, mp)
	for i in range(N_SRV):
		datacenter.newServerPlugin()
		info_leaf = datacenter.leafPool.getCurrentInfo()
		info_mgmt = datacenter.mgmtPool.getCurrentInfo()
		print('第 %d 台SV追加済み。IF利用状況：Leaf(%d/%d), Mgmt(%d/%d)' % \
			(i+1, info_leaf[0], info_leaf[1], info_mgmt[0], info_mgmt[1]))
	print('----------------')
	datacenter.showPoolInfo()
	print('※ Leaf組が対称であることが前提です。')


if __name__ == '__main__':
	## 使用方法：python3 hms.py <サーバ追加台数>
	print('Build: ' + BUILD)
	main()