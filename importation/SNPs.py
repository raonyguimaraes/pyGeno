import urllib, shutil

from ConfigParser import SafeConfigParser
import pyGeno.configuration as conf
from pyGeno.SNP import *
from pyGeno.tools.ProgressBar import ProgressBar
from pyGeno.tools.io import printf
from Genomes import _decompressPackage, _getFile

from pyGeno.tools.parsers.CasavaTools import SNPsTxtFile
from pyGeno.tools.parsers.VCFTools import VCFFile

def importSNPs(packageFile) :
	"""The big wrapper, this function should detect the SNP type by the package manifest and then launch the corresponding function"""
	packageDir = _decompressPackage(packageFile)

	parser = SafeConfigParser()
	parser.read(os.path.normpath(packageDir+'/manifest.ini'))
	packageInfos = parser.items('package_infos')

	setName = parser.get('set_infos', 'name')
	typ = parser.get('set_infos', 'type')+'SNP'
	specie = parser.get('set_infos', 'specie').lower()
	genomeSource = parser.get('set_infos', 'source')
	snpsFileTmp = parser.get('snps', 'filename').strip()
	snpsFile = _getFile(parser.get('snps', 'filename'), packageDir)
	
	try :
		SMaster = SNPMaster(setName = setName)
		raise ValueError("There's already a SNP set by the name %s. Use deleteSNPs() to remove it first" %setName)
	except KeyError :
		if typ == 'CasavaSNP' :
			return _importSNPs_CasavaSNP(setName, specie, genomeSource, snpsFile)
		elif typ == 'dbSNPSNP' :
			return _importSNPs_dbSNPSNP(setName, specie, genomeSource, snpsFile)
		elif typ == 'TopHatSNP' :
			return _importSNPs_TopHatSNP(setName, specie, genomeSource, snpsFile)
		else :
			raise FutureWarning('Unknown SNP type in manifest %s' % typ)
	
	shutil.rmtree(packageDir)

def deleteSNPs(setName) :
	con = conf.db
	try :
		SMaster = SNPMaster(setName = setName)
		con.beginTransaction()
		SNPType = SMaster.SNPType
		con.delete(SNPType, 'setName = ?', (setName,))
		SMaster.delete()
		con.endTransaction()
	except KeyError :
		#raise KeyError("can't delete the setName %s because i can't find it in SNPMaster, maybe there's not set by that name" % setName)
		printf("can't delete the setName %s because i can't find it in SNPMaster, maybe there's no set by that name" % setName)
		return False
	return True

def _importSNPs_CasavaSNP(setName, specie, genomeSource, snpsFile) :
	"This function will also create an index on start->chromosomeNumber->setName. Warning : pyGeno positions are 0 based"
	printf('importing SNP set %s for specie %s...' % (setName, specie))

	snpData = SNPsTxtFile(snpsFile)
	
	CasavaSNP.dropIndex(('start', 'chromosomeNumber', 'setName'))
	conf.db.beginTransaction()
	
	pBar = ProgressBar(len(snpData))
	pLabel = ''
	currChrNumber = None
	for snpEntry in snpData :
		tmpChr = snpEntry['chromosomeNumber']
		if tmpChr != currChrNumber :
			currChrNumber = tmpChr
			pLabel = 'Chr %s...' % currChrNumber

		snp = CasavaSNP()
		#snp.chromosomeNumber = currChrNumber
		snp.specie = specie
		snp.setName = setName
		#first column: chro, second first of range (identical to second column)
		for f in snp.getFields() :
			try :
				setattr(snp, f, snpEntry[f])
			except KeyError :
				if f != 'specie' and f != 'setName' :
					printf("Warning filetype as no key %s", f)
		snp.start -= 1
		snp.end -= 1
		snp.save()
		pBar.update(label = pLabel)

	pBar.close()
	
	snpMaster = SNPMaster()
	snpMaster.set(setName = setName, SNPType = 'CasavaSNP', specie = specie)
	snpMaster.save()

	printf('saving...')
	conf.db.endTransaction()
	printf('creating indexes...')
	CasavaSNP.ensureGlobalIndex(('start', 'chromosomeNumber', 'setName'))
	printf('importation of SNP set %s for specie %s done.' %(setName, specie))
	
	return True

def _importSNPs_dbSNPSNP(setName, specie, genomeSource, snpsFile) :
	"This function will also create an index on start->chromosomeNumber->setName. Warning : pyGeno positions are 0 based"
	snpData = VCFFile(snpsFile, gziped = True, stream = True)
	dbSNPSNP.dropIndex(('start', 'chromosomeNumber', 'setName'))
	conf.db.beginTransaction()
	pBar = ProgressBar()
	pLabel = ''
	for snpEntry in snpData :
		pBar.update(label = 'Chr %s, %s...' %  (snpEntry['#CHROM'], snpEntry['ID']))
		
		snp = dbSNPSNP()
		for f in snp.getFields() :
			try :
				setattr(snp, f, snpEntry[f])
			except KeyError :
				pass
		snp.chromosomeNumber = snpEntry['#CHROM']
		snp.specie = specie
		snp.setName = setName
		snp.start = snpEntry['POS']-1
		snp.alt = snpEntry['ALT']
		snp.end = snp.start+len(snp.alt)
		snp.save()
	
	pBar.close()
	
	snpMaster = SNPMaster()
	snpMaster.set(setName = setName, SNPType = 'dbSNPSNP', specie = specie)
	snpMaster.save()
	
	printf('saving...')
	conf.db.endTransaction()
	printf('creating indexes...')
	dbSNPSNP.ensureGlobalIndex(('start', 'chromosomeNumber', 'setName'))
	printf('importation of SNP set %s for specie %s done.' %(setName, specie))

	return True
	
def _importSNPs_TopHatSNP(setName, specie, genomeSource, snpsFile) :
	raise FutureWarning('Not implemented yet')
	
if __name__ == "__main__" :
	print "ex : importSNPs('ARN_Subj10012.tar.gz')"
	print "ex : importSNPs('dbSNP138.tar.gz')"
